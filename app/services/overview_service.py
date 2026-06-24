from __future__ import annotations

from app.core.freshness import LIVE_WINDOW_DAYS, is_inside_live_window
from app.services.incident_service import list_clusters
from app.services.scoring_service import score_categories

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}
FRESHNESS_RANK = {"recent": 3, "aging": 2, "stale": 1, "unknown": 0}


def _is_recent_cluster(cluster: dict, *, window_days: int = LIVE_WINDOW_DAYS) -> bool:
    return is_inside_live_window(cluster.get("last_seen_at", ""), live_window_days=window_days)


def _sort_transport_clusters(clusters: list[dict], sort_by: str) -> list[dict]:
    if sort_by == "freshest":
        return sorted(
            clusters,
            key=lambda item: (
                item.get("last_seen_at", ""),
                item.get("confidence_score", 0),
                SEVERITY_RANK.get(item.get("severity", "low"), 0),
            ),
            reverse=True,
        )
    return sorted(
        clusters,
        key=lambda item: (
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


def get_trafficmy_incidents(
    *,
    sort_by: str = "strongest",
    confidence_band: str | None = None,
    severity: str | None = None,
    entity: str | None = None,
    location: str | None = None,
    include_stale: bool = False,
) -> dict:
    clusters = list_clusters(
        category="transport",
        severity=severity,
        confidence_band=confidence_band,
    )
    stale_hidden_count = 0
    if not include_stale:
        recent = [cluster for cluster in clusters if _is_recent_cluster(cluster)]
        stale_hidden_count = len(clusters) - len(recent)
        clusters = recent
    if entity:
        clusters = [cluster for cluster in clusters if cluster.get("entity") == entity]
    if location:
        clusters = [cluster for cluster in clusters if cluster.get("location") == location]
    clusters = _sort_transport_clusters(clusters, sort_by=sort_by)
    return {
        "product": "TrafficMY",
        "sort_by": sort_by,
        "filters": {
            "confidence_band": confidence_band,
            "severity": severity,
            "entity": entity,
            "location": location,
            "include_stale": include_stale,
        },
        "live_window_days": LIVE_WINDOW_DAYS,
        "stale_hidden_count": stale_hidden_count,
        "count": len(clusters),
        "items": clusters,
    }


def get_trafficmy_overview(*, include_stale: bool = False) -> dict:
    all_clusters = list_clusters(category="transport")
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
    for cluster in clusters:
        ent = cluster.get("entity")
        loc = cluster.get("location")
        if ent:
            entity_counts[ent] = entity_counts.get(ent, 0) + cluster.get("volume", 1)
        if loc:
            location_counts[loc] = location_counts.get(loc, 0) + cluster.get("volume", 1)
    transport_entities = [
        {"name": name, "count": count}
        for name, count in sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    transport_locations = [
        {"name": name, "count": count}
        for name, count in sorted(location_counts.items(), key=lambda x: x[1], reverse=True)
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
        "top_incidents": clusters[:5],
        "transport_entities": transport_entities,
        "transport_locations": transport_locations,
    }
