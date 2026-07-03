from __future__ import annotations

from collections import Counter

import requests

from app.core.files import load_yaml

GTFS_CONFIG = load_yaml("gtfs.yaml")
REALTIME_BASE = GTFS_CONFIG.get(
    "realtime_base",
    "https://api.data.gov.my/gtfs-realtime/vehicle-position/prasarana",
)
BUS_NETWORKS = [
    name for name, meta in GTFS_CONFIG.get("networks", {}).items() if meta.get("mode") == "bus"
]
DEFAULT_BUS_NETWORK = "rapid-bus-kl"
# Malaysia bounds — same as map_service (KV-focused live bus layer).
_MY_BOUNDS = {"south": 0.85, "north": 7.5, "west": 99.0, "east": 119.5}


def _in_malaysia(lat: float, lon: float) -> bool:
    return (
        _MY_BOUNDS["south"] <= lat <= _MY_BOUNDS["north"]
        and _MY_BOUNDS["west"] <= lon <= _MY_BOUNDS["east"]
    )


def _parse_feed(network: str):
    if network == "ktmb":
        url = "https://api.data.gov.my/gtfs-realtime/vehicle-position/ktmb"
    else:
        url = f"{REALTIME_BASE}?category={network}"
    try:
        response = requests.get(url, timeout=25)
        response.raise_for_status()
    except Exception:
        return None
    if len(response.content) < 20:
        return None
    try:
        from google.transit import gtfs_realtime_pb2
    except ImportError:
        return None
    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(response.content)
    except Exception:
        return None
    return feed


def fetch_vehicle_counts(network: str) -> Counter:
    feed = _parse_feed(network)
    if feed is None:
        return Counter()
    counts: Counter = Counter()
    for entity in feed.entity:
        vehicle = entity.vehicle
        if not vehicle or not vehicle.trip or not vehicle.trip.route_id:
            continue
        counts[vehicle.trip.route_id] += 1
    return counts


def fetch_bus_vehicle_positions(
    network: str = DEFAULT_BUS_NETWORK,
    *,
    limit: int = 80,
) -> list[dict]:
    """Live bus GPS from data.gov.my GTFS-RT — pattern inspired by weareblahs/bus."""
    feed = _parse_feed(network)
    if feed is None:
        return []
    from datetime import UTC, datetime

    vehicles: list[dict] = []
    now = datetime.now(UTC)
    for entity in feed.entity:
        vehicle = entity.vehicle
        if not vehicle or not vehicle.position:
            continue
        lat = vehicle.position.latitude
        lon = vehicle.position.longitude
        if not _in_malaysia(lat, lon):
            continue
        route_id = vehicle.trip.route_id if vehicle.trip else ""
        ts = None
        if vehicle.timestamp:
            ts = datetime.fromtimestamp(vehicle.timestamp, tz=UTC).isoformat().replace("+00:00", "Z")
        age_sec = None
        if vehicle.timestamp:
            age_sec = max(0, int(now.timestamp() - vehicle.timestamp))
        vehicles.append(
            {
                "id": entity.id or f"{route_id}:{len(vehicles)}",
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "route_id": route_id,
                "bearing": vehicle.position.bearing if vehicle.position.bearing else None,
                "network": network,
                "updated_at": ts,
                "age_seconds": age_sec,
                "source": "gtfs_rt",
            }
        )
        if len(vehicles) >= limit:
            break
    return vehicles


def fetch_rail_vehicle_positions(*, limit: int = 40) -> list[dict]:
    """Live rail GPS from data.gov.my KTFS-RT (KTMB)."""
    feed = _parse_feed("ktmb")
    if feed is None:
        return []
    from datetime import UTC, datetime

    vehicles: list[dict] = []
    now = datetime.now(UTC)
    for entity in feed.entity:
        vehicle = entity.vehicle
        if not vehicle or not vehicle.position:
            continue
        lat = vehicle.position.latitude
        lon = vehicle.position.longitude
        if not _in_malaysia(lat, lon):
            continue
        route_id = vehicle.trip.route_id if vehicle.trip else ""
        label = vehicle.vehicle.label if vehicle.vehicle and vehicle.vehicle.label else route_id
        ts = None
        if vehicle.timestamp:
            ts = datetime.fromtimestamp(vehicle.timestamp, tz=UTC).isoformat().replace("+00:00", "Z")
        age_sec = None
        if vehicle.timestamp:
            age_sec = max(0, int(now.timestamp() - vehicle.timestamp))
        vehicles.append(
            {
                "id": entity.id or f"ktmb:{route_id}:{len(vehicles)}",
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "route_id": route_id,
                "label": label,
                "bearing": vehicle.position.bearing if vehicle.position.bearing else None,
                "network": "ktmb",
                "mode": "rail",
                "updated_at": ts,
                "age_seconds": age_sec,
                "source": "gtfs_rt",
            }
        )
        if len(vehicles) >= limit:
            break
    return vehicles


def fetch_all_bus_vehicle_counts() -> dict[str, Counter]:
    out: dict[str, Counter] = {}
    for network in BUS_NETWORKS:
        out[network] = fetch_vehicle_counts(network)
    return out
