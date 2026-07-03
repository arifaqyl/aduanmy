from __future__ import annotations

from app.core.freshness import LIVE_WINDOW_DAYS, is_inside_live_window
from app.core.malaysia_transport_scope import is_malaysia_transport_cluster
from app.pipeline.extract import transport_incident_signal_ok, transport_rider_signal_worthwhile
from app.services.incident_service import list_clusters
from app.services.scoring_service import score_categories

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}
FRESHNESS_RANK = {"recent": 3, "aging": 2, "stale": 1, "unknown": 0}
SOURCE_GROUP_SOCIAL = {"threads", "reddit", "x", "rss"}
SOURCE_GROUP_GPS = {"gtfs_rt"}
RIDER_SIGNAL_SOURCES = {"threads", "reddit", "rss"}


def _cluster_sources(cluster: dict) -> set[str]:
    return {part.strip() for part in (cluster.get("sources") or "").split(",") if part.strip()}


def _matches_source_group(cluster: dict, source_group: str) -> bool:
    sources = _cluster_sources(cluster)
    if not sources:
        return False
    if source_group == "all":
        return True
    if source_group == "gps":
        return sources.issubset(SOURCE_GROUP_GPS)
    # Default: human/public complaint signals — hide pure GPS telemetry rows.
    return bool(sources & SOURCE_GROUP_SOCIAL)


def _is_real_transport_complaint(cluster: dict) -> bool:
    if cluster.get("subcategory") == "line_info":
        return False
    sources = _cluster_sources(cluster)
    if sources == {"gtfs_rt"}:
        return True
    text = cluster.get("example_text") or ""
    if not text.strip():
        return False
    entity = cluster.get("entity") or ""
    if sources & RIDER_SIGNAL_SOURCES:
        return transport_rider_signal_worthwhile(text, entity)
    return transport_incident_signal_ok(text, entity)


def _matches_freshness_band(cluster: dict, freshness_band: str) -> bool:
    if freshness_band == "all":
        return True
    bucket = cluster.get("freshness_bucket", "unknown")
    if freshness_band == "recent":
        return bucket == "recent"
    if freshness_band == "aging":
        return bucket == "aging"
    return bucket == freshness_band


def _is_recent_cluster(cluster: dict, *, window_days: int = LIVE_WINDOW_DAYS) -> bool:
    return is_inside_live_window(cluster.get("last_seen_at", ""), live_window_days=window_days)


def _sort_transport_clusters(clusters: list[dict], sort_by: str) -> list[dict]:
    if sort_by == "freshest":
        return sorted(
            clusters,
            key=lambda item: (
                item.get("last_seen_at", ""),
                not _telemetry_only(item),
                item.get("confidence_score", 0),
                SEVERITY_RANK.get(item.get("severity", "low"), 0),
            ),
            reverse=True,
        )
    return sorted(
        clusters,
        key=lambda item: (
            not _telemetry_only(item),
            item.get("confidence_band") == "strong",
            item.get("confidence_band") == "reasonable",
            FRESHNESS_RANK.get(item.get("freshness_bucket", "unknown"), 0),
            item.get("confidence_score", 0),
            SEVERITY_RANK.get(item.get("severity", "low"), 0),
            item.get("volume", 0),
            item.get("last_seen_at", ""),
        ),
        reverse=True,
    )


def _telemetry_only(cluster: dict) -> bool:
    sources = _cluster_sources(cluster)
    return sources == {"gtfs_rt"}


def _top_incident_slice(clusters: list[dict], *, limit: int = 5) -> list[dict]:
    quality_clusters = [
        cluster for cluster in clusters if cluster.get("confidence_band") in {"strong", "reasonable"}
    ]
    if quality_clusters:
        return quality_clusters[:limit]
    return clusters[:limit]


def get_trafficmy_incidents(
    *,
    sort_by: str = "strongest",
    confidence_band: str | None = None,
    severity: str | None = None,
    entity: str | None = None,
    location: str | None = None,
    state: str | None = None,
    mode: str | None = None,
    source_group: str = "social",
    freshness_band: str = "recent",
    quality_only: bool = True,
    include_stale: bool = False,
    malaysia_only: bool = True,
) -> dict:
    clusters = list_clusters(
        category="transport",
        severity=severity,
        confidence_band=confidence_band,
    )
    clusters = [cluster for cluster in clusters if _matches_source_group(cluster, source_group)]
    if malaysia_only:
        clusters = [cluster for cluster in clusters if is_malaysia_transport_cluster(cluster)]
    if quality_only:
        clusters = [cluster for cluster in clusters if _is_real_transport_complaint(cluster)]
    clusters = [cluster for cluster in clusters if _matches_freshness_band(cluster, freshness_band)]
    stale_hidden_count = 0
    if not include_stale:
        recent = [cluster for cluster in clusters if _is_recent_cluster(cluster)]
        stale_hidden_count = len(clusters) - len(recent)
        clusters = recent
    if entity:
        clusters = [cluster for cluster in clusters if cluster.get("entity") == entity]
    if location:
        clusters = [cluster for cluster in clusters if cluster.get("location") == location]
    if state:
        clusters = [cluster for cluster in clusters if cluster.get("state") == state]
    if mode:
        clusters = [cluster for cluster in clusters if cluster.get("subcategory") == mode]
    clusters = _sort_transport_clusters(clusters, sort_by=sort_by)
    return {
        "product": "TrafficMY",
        "sort_by": sort_by,
        "filters": {
            "confidence_band": confidence_band,
            "severity": severity,
            "entity": entity,
            "location": location,
            "state": state,
            "mode": mode,
            "source_group": source_group,
            "freshness_band": freshness_band,
            "quality_only": quality_only,
            "include_stale": include_stale,
            "malaysia_only": malaysia_only,
        },
        "live_window_days": LIVE_WINDOW_DAYS,
        "stale_hidden_count": stale_hidden_count,
        "count": len(clusters),
        "items": clusters,
    }


def get_trafficmy_overview(
    *,
    include_stale: bool = False,
    source_group: str = "social",
    quality_only: bool = True,
    malaysia_only: bool = True,
) -> dict:
    all_clusters = list_clusters(category="transport")
    all_clusters = [cluster for cluster in all_clusters if _matches_source_group(cluster, source_group)]
    if malaysia_only:
        all_clusters = [cluster for cluster in all_clusters if is_malaysia_transport_cluster(cluster)]
    if quality_only:
        all_clusters = [cluster for cluster in all_clusters if _is_real_transport_complaint(cluster)]
    stale_hidden_count = 0
    if include_stale:
        clusters = all_clusters
    else:
        clusters = [cluster for cluster in all_clusters if _is_recent_cluster(cluster)]
        stale_hidden_count = len(all_clusters) - len(clusters)
    clusters = _sort_transport_clusters(clusters, sort_by="strongest")
    strong = [cluster for cluster in clusters if cluster["confidence_band"] == "strong"]
    reasonable = [cluster for cluster in clusters if cluster["confidence_band"] == "reasonable"]
    weak = [cluster for cluster in clusters if cluster["confidence_band"] == "weak"]
    scores = score_categories()
    transport_score = next((row for row in scores if row["category"] == "transport"), None)

    # Derive entities and locations from live transport clusters — no hardcoded allowlist
    entity_counts: dict[str, int] = {}
    location_counts: dict[str, int] = {}
    state_counts: dict[str, int] = {}
    mode_counts: dict[str, int] = {}
    for cluster in clusters:
        ent = cluster.get("entity")
        loc = cluster.get("location")
        st = cluster.get("state")
        md = cluster.get("subcategory")
        if ent:
            entity_counts[ent] = entity_counts.get(ent, 0) + cluster.get("volume", 1)
        if loc:
            location_counts[loc] = location_counts.get(loc, 0) + cluster.get("volume", 1)
        if st:
            state_counts[st] = state_counts.get(st, 0) + cluster.get("volume", 1)
        if md:
            mode_counts[md] = mode_counts.get(md, 0) + cluster.get("volume", 1)
    transport_entities = [
        {"name": name, "count": count}
        for name, count in sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    transport_locations = [
        {"name": name, "count": count}
        for name, count in sorted(location_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    transport_states = [
        {"name": name, "count": count}
        for name, count in sorted(state_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    return {
        "product": "TrafficMY",
        "summary": {
            "transport_cluster_count": len(clusters),
            "strong_cluster_count": len(strong),
            "reasonable_cluster_count": len(reasonable),
            "weak_cluster_count": len(weak),
            "top_wedge_score": transport_score,
            "live_window_days": LIVE_WINDOW_DAYS,
            "stale_hidden_count": stale_hidden_count,
            "include_stale": include_stale,
        },
        "top_incidents": _top_incident_slice(clusters),
        "transport_entities": transport_entities,
        "transport_locations": transport_locations,
        "transport_states": transport_states,
        "transport_modes": [
            {"name": name, "count": count}
            for name, count in sorted(mode_counts.items(), key=lambda x: x[1], reverse=True)
        ],
    }
