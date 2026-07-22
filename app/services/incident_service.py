from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from app.core.freshness import LIVE_WINDOW_DAYS, classify_freshness, is_inside_live_window, parse_dt
from app.core.transport_lines import is_official_grounding_row, match_transport_line
from app.db.session import connect, init_db

SOURCE_WEIGHTS = {
    "x": 0.9,
    "threads": 0.85,
    "reddit": 0.8,
    "rss": 0.75,
    "gtfs_rt": 0.85,
    "official": 1.0,
}

GENERIC_TRANSPORT_ENTITIES = {"rapidkl", "lrt", "mrt", "ktm"}
MEDIA_HANDLES = {"thesundaily", "thestaronline", "themalaymail", "theedgemalaysia"}
OFFICIAL_CORROBORATION_WINDOW = timedelta(hours=24)

SEVERITY_BONUS = {
    "high": 1.5,
    "medium": 1.0,
    "low": 0.4,
}

def _event_timestamp(item: dict) -> str:
    return item.get("created_at") or item.get("inserted_at") or ""


def _parse_dt(value: str | None) -> datetime | None:
    return parse_dt(value)


def list_complaints(limit: int = 100) -> list[dict]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT source_platform, post_id, url, author_handle, created_at,
                   raw_text, normalized_text, detected_language_mix, category,
                   entity, location, state, severity, confidence, cluster_id
            FROM complaints
            ORDER BY inserted_at DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _official_grounding_rows() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT category, entity, location, normalized_text, source_platform, url,
                   author_handle, created_at, inserted_at
            FROM complaints
            WHERE source_platform IN ('official', 'rss')
            """
        ).fetchall()
    return [dict(row) for row in rows if is_official_grounding_row(dict(row))]


def _official_match_for_cluster(cluster: dict, official_rows: list[dict]) -> dict | None:
    """Return the matching official/RSS notice, or None."""
    category = cluster.get("category", "")
    entity = cluster.get("entity", "")
    location = cluster.get("location", "")
    cluster_line = match_transport_line(cluster) if category == "transport" else None
    cluster_time = parse_dt(cluster.get("last_seen_at") or cluster.get("first_seen_at"))
    for row in official_rows:
        if row["category"] != category:
            continue
        row_time = parse_dt(row.get("created_at") or row.get("inserted_at"))
        if cluster_time is None or row_time is None:
            continue
        if abs(cluster_time - row_time) > OFFICIAL_CORROBORATION_WINDOW:
            continue
        row_entity = row.get("entity") or ""
        row_location = row.get("location") or ""
        hit = False
        if cluster_line and category == "transport":
            row_line = match_transport_line(row)
            if row_line and row_line == cluster_line:
                hit = True
        if not hit:
            if entity:
                if not row_entity or row_entity != entity:
                    continue
            elif row_entity:
                continue
            if location and row_location:
                if row_location != location:
                    continue
            elif location:
                if not (
                    category == "transport"
                    and entity
                    and row_entity
                    and row_entity.lower() not in GENERIC_TRANSPORT_ENTITIES
                ):
                    continue
            elif row_location:
                continue
            hit = True
        if not hit:
            continue
        title = str(row.get("normalized_text") or row.get("raw_text") or "Official notice").strip()
        title = re.sub(r"\s+", " ", title)
        if len(title) > 140:
            title = title[:139].rstrip() + "…"
        return {
            "source_platform": row.get("source_platform") or "official",
            "title": title,
            "url": row.get("url") or "",
            "created_at": row.get("created_at") or row.get("inserted_at") or "",
            "entity": row_entity,
            "location": row_location,
        }
    return None


def _cluster_has_official_match(cluster: dict, official_rows: list[dict]) -> bool:
    return _official_match_for_cluster(cluster, official_rows) is not None


def _normalize_api_timestamp(value: str | None) -> str:
    parsed = parse_dt(value)
    if parsed is None:
        return value or ""
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _telemetry_only(cluster: dict) -> bool:
    sources = {part.strip() for part in (cluster.get("sources") or "").split(",") if part.strip()}
    return sources == {"gtfs_rt"}


def _score_cluster_confidence(cluster: dict) -> tuple[float, str]:
    sources = [part.strip() for part in (cluster.get("sources") or "").split(",") if part.strip()]
    source_count = len(set(sources))
    source_weight_total = round(sum(SOURCE_WEIGHTS.get(source, 0.7) for source in set(sources)), 2)
    base = 0.0
    base += min(cluster.get("volume", 0), 3) * 1.0
    base += max(source_count - 1, 0) * 1.5
    base += SEVERITY_BONUS.get(cluster.get("severity", "low"), 0.4)
    if cluster.get("entity"):
        base += 0.7
    if cluster.get("location"):
        base += 0.6
    if cluster.get("corroborated_by_official"):
        base += 1.25
    base += max(source_weight_total - 0.8, 0) * 0.35
    if _telemetry_only(cluster):
        # GPS gaps are hints, not verified incidents — keep below social complaints.
        base = min(base, 4.8)
        if not cluster.get("corroborated_by_official"):
            base = min(base, 3.2)
        if cluster.get("freshness_bucket") != "recent":
            base = min(base, 2.0)
    elif "threads" in sources and cluster.get("freshness_bucket") == "recent":
        base += 1.5
    score = round(base, 2)
    if score >= 5.5:
        band = "strong"
    elif score >= 3.5:
        band = "reasonable"
    else:
        band = "weak"
    return score, band


def _classify_source_role(source_platform: str, author_handle: str = "") -> str:
    if source_platform == "official":
        return "official_grounding"
    if source_platform == "rss":
        return "media_report"
    if source_platform == "gtfs_rt":
        return "telemetry"
    if (author_handle or "").lower() in MEDIA_HANDLES:
        return "media_report"
    return "public_signal"


def _cluster_source_roles(cluster: dict) -> list[str]:
    sources = [part.strip() for part in (cluster.get("sources") or "").split(",") if part.strip()]
    handles = [part.strip() for part in (cluster.get("author_handles") or "").split(",") if part.strip()]
    media_handles = {handle.lower() for handle in handles if handle.lower() in MEDIA_HANDLES}
    roles: set[str] = set()
    if "official" in sources:
        roles.add("official_grounding")
    if "rss" in sources:
        roles.add("media_report")
    if "gtfs_rt" in sources:
        roles.add("telemetry")
    if media_handles:
        roles.add("media_report")
    if any(source in {"x", "reddit"} for source in sources):
        roles.add("public_signal")
    if "threads" in sources and (not handles or any(handle.lower() not in MEDIA_HANDLES for handle in handles)):
        roles.add("public_signal")
    ordered = ["public_signal", "media_report", "telemetry", "official_grounding"]
    return [role for role in ordered if role in roles]


def _enrich_clusters(clusters: list[dict]) -> list[dict]:
    official_rows = _official_grounding_rows()
    for cluster in clusters:
        official_match = _official_match_for_cluster(cluster, official_rows)
        cluster["corroborated_by_official"] = official_match is not None
        cluster["official_match"] = official_match
        score, band = _score_cluster_confidence(cluster)
        cluster["confidence_score"] = score
        cluster["confidence_band"] = band
        roles = _cluster_source_roles(cluster)
        if cluster["corroborated_by_official"] and "official_grounding" not in roles:
            roles.append("official_grounding")
        cluster["source_roles"] = roles
        cluster["first_seen_at"] = _normalize_api_timestamp(cluster.get("first_seen_at", ""))
        cluster["last_seen_at"] = _normalize_api_timestamp(cluster.get("last_seen_at", ""))
        freshness_bucket, age_days = classify_freshness(cluster.get("last_seen_at", ""))
        cluster["freshness_bucket"] = freshness_bucket
        cluster["age_days"] = age_days
    return clusters


def list_clusters(
    *,
    include_official: bool = False,
    category: str | None = None,
    severity: str | None = None,
    confidence_band: str | None = None,
) -> list[dict]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            WITH clustered AS (
                SELECT cluster_id,
                       category,
                       source_platform,
                       author_handle,
                       created_at,
                       entity,
                       location,
                       state,
                       subcategory,
                       url,
                       normalized_text,
                       inserted_at,
                       CASE source_platform
                           WHEN 'x' THEN 0.9
                           WHEN 'threads' THEN 0.85
                           WHEN 'reddit' THEN 0.8
                           WHEN 'rss' THEN 0.75
                           WHEN 'gtfs_rt' THEN 0.85
                           WHEN 'official' THEN 1.0
                           ELSE 0.7
                       END AS source_weight,
                       CASE severity
                           WHEN 'high' THEN 3
                           WHEN 'medium' THEN 2
                           ELSE 1
                       END AS severity_rank
                FROM complaints
                WHERE (? = 1 OR source_platform != 'official')
            )
            SELECT cluster_id, category, COUNT(*) AS volume,
                   GROUP_CONCAT(DISTINCT source_platform) AS sources,
                   GROUP_CONCAT(DISTINCT author_handle) AS author_handles,
                   COUNT(DISTINCT source_platform) AS source_count,
                   ROUND(SUM(source_weight), 2) AS source_weight_total,
                   CASE MAX(severity_rank)
                       WHEN 3 THEN 'high'
                       WHEN 2 THEN 'medium'
                       ELSE 'low'
                   END AS severity,
                   MIN(COALESCE(datetime(NULLIF(created_at, '')), inserted_at)) AS first_seen_at,
                   MAX(COALESCE(datetime(NULLIF(created_at, '')), inserted_at)) AS last_seen_at,
                   MAX(entity) AS entity,
                   MAX(location) AS location,
                   MAX(NULLIF(state, '')) AS state,
                   MAX(NULLIF(subcategory, '')) AS subcategory,
                   MIN(url) AS example_url,
                   MIN(SUBSTR(normalized_text, 1, 180)) AS example_text
            FROM clustered
            GROUP BY cluster_id, category
            ORDER BY volume DESC, category ASC
            """,
            (1 if include_official else 0,),
        ).fetchall()
    clusters = _enrich_clusters([dict(row) for row in rows])
    if category:
        clusters = [cluster for cluster in clusters if cluster["category"] == category]
    if severity:
        clusters = [cluster for cluster in clusters if cluster["severity"] == severity]
    if confidence_band:
        clusters = [cluster for cluster in clusters if cluster["confidence_band"] == confidence_band]
    return clusters


def get_cluster_detail(cluster_id: str, include_official: bool = False) -> dict | None:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT source_platform, post_id, url, author_handle, created_at,
                   raw_text, normalized_text, detected_language_mix, category,
                   entity, location, state, severity, confidence, cluster_id
            FROM complaints
            WHERE cluster_id = ?
              AND (? = 1 OR source_platform != 'official')
            ORDER BY inserted_at DESC, id DESC
            """,
            (cluster_id, 1 if include_official else 0),
        ).fetchall()
    items = [dict(row) for row in rows]
    if not items:
        return None

    base_cluster = _enrich_clusters(
        [
            {
                "cluster_id": cluster_id,
                "category": items[0]["category"],
                "volume": len(items),
                "sources": ",".join(sorted({item["source_platform"] for item in items})),
                "author_handles": ",".join(sorted({item["author_handle"] for item in items if item.get("author_handle")})),
                "source_count": len({item["source_platform"] for item in items}),
                "source_weight_total": round(sum(SOURCE_WEIGHTS.get(item["source_platform"], 0.7) for item in items), 2),
                "severity": max(items, key=lambda item: {"low": 1, "medium": 2, "high": 3}.get(item["severity"], 0))["severity"],
                "first_seen_at": min((_event_timestamp(item) for item in items), default=""),
                "last_seen_at": max((_event_timestamp(item) for item in items), default=""),
                "entity": items[0]["entity"],
                "location": items[0]["location"],
                "example_url": items[0]["url"],
                "example_text": items[0]["normalized_text"][:180],
            }
        ]
    )[0]

    source_breakdown: dict[str, int] = {}
    for item in items:
        source_breakdown[item["source_platform"]] = source_breakdown.get(item["source_platform"], 0) + 1

    return {
        "cluster": base_cluster,
        "source_breakdown": source_breakdown,
        "items": items,
    }
