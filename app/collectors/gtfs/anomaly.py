from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from app.collectors.common import make_post_id
from app.collectors.gtfs.rt_client import fetch_all_bus_vehicle_counts
from app.core.files import load_yaml
from app.db.gtfs_store import top_routes_by_trips

MYT = timezone(timedelta(hours=8))
GTFS_CONFIG = load_yaml("gtfs.yaml")
NETWORK_META = GTFS_CONFIG.get("networks", {})
MIN_TRIP_RANK = int(GTFS_CONFIG.get("anomaly", {}).get("min_trip_rank", 30))


def _in_service_window() -> bool:
    hour = datetime.now(MYT).hour
    return 6 <= hour < 23


def detect_route_anomalies() -> list[dict]:
    if not _in_service_window():
        return []
    vehicle_map = fetch_all_bus_vehicle_counts()
    if not vehicle_map or not any(len(c) > 0 for c in vehicle_map.values()):
        return []
    rows: list[dict] = []
    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    for network, counts in vehicle_map.items():
        meta = NETWORK_META.get(network, {})
        label = meta.get("label", network)
        state = meta.get("state", "")
        top_routes = top_routes_by_trips(network, limit=MIN_TRIP_RANK)
        for route in top_routes:
            route_id = route["route_id"]
            active = counts.get(route_id, 0)
            if active > 0:
                continue
            short = route["route_short_name"]
            long_name = route["route_long_name"]
            text = (
                f"GTFS anomaly: {label} route {short} ({long_name}) shows no active vehicles "
                f"during service hours — possible disruption or GPS gap"
            )
            rows.append(
                {
                    "source_platform": "gtfs_rt",
                    "post_id": make_post_id(f"gtfs:{network}:{route_id}:{now_iso[:10]}"),
                    "url": "https://developer.data.gov.my/realtime-api/gtfs-realtime",
                    "author_handle": f"gtfs:{network}",
                    "created_at": now_iso,
                    "raw_text": text,
                    "query": network,
                    "seed_category": "transport",
                    "subcategory": "bus",
                    "entity": short,
                    "state": state,
                    "severity": "medium",
                    "network": network,
                    "route_id": route_id,
                }
            )
    return rows[:12]
