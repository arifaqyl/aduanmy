from __future__ import annotations

import csv
import io
import zipfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests

from app.core.config import settings
from app.core.files import load_yaml, report_path
from app.db.gtfs_store import upsert_routes

GTFS_CONFIG = load_yaml("gtfs.yaml")
NETWORKS: dict = GTFS_CONFIG.get("networks", {})
STATIC_BASE = GTFS_CONFIG.get("static_base", "https://api.data.gov.my/gtfs-static/prasarana")
CACHE_HOURS = int(GTFS_CONFIG.get("anomaly", {}).get("cache_hours", 24))


def _cache_dir() -> Path:
    path = Path(settings.data_dir) / "gtfs" / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path(network: str) -> Path:
    return _cache_dir() / f"{network}.zip"


def _cache_fresh(network: str) -> bool:
    path = _cache_path(network)
    if not path.exists():
        return False
    age = datetime.now(UTC) - datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return age < timedelta(hours=CACHE_HOURS)


def download_static(network: str, *, force: bool = False) -> Path:
    path = _cache_path(network)
    if not force and _cache_fresh(network):
        return path
    url = f"{STATIC_BASE}?category={network}"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def parse_routes_from_zip(network: str, zip_path: Path) -> list[dict]:
    meta = NETWORKS.get(network, {})
    mode = meta.get("mode", "bus")
    state = meta.get("state", "")
    with zipfile.ZipFile(zip_path) as zf:
        routes = list(csv.DictReader(io.TextIOWrapper(zf.open("routes.txt"), encoding="utf-8-sig")))
        trips = list(csv.DictReader(io.TextIOWrapper(zf.open("trips.txt"), encoding="utf-8-sig")))
    trip_counts = Counter(t.get("route_id", "") for t in trips)
    out: list[dict] = []
    for route in routes:
        route_id = route.get("route_id", "")
        if not route_id:
            continue
        route_type = int(route.get("route_type") or 3)
        out.append(
            {
                "network": network,
                "route_id": route_id,
                "route_short_name": (route.get("route_short_name") or route_id).strip(),
                "route_long_name": (route.get("route_long_name") or "").strip(),
                "route_type": route_type,
                "trip_count": trip_counts.get(route_id, 0),
                "mode": "rail" if route_type in {0, 1, 2} else mode,
                "state": state,
            }
        )
    return out


def sync_static_catalog(*, force: bool = False) -> dict[str, int]:
    counts: dict[str, int] = {}
    for network in NETWORKS:
        try:
            zip_path = download_static(network, force=force)
            routes = parse_routes_from_zip(network, zip_path)
            counts[network] = upsert_routes(routes)
        except Exception:
            counts[network] = 0
    report_path("latest_gtfs_sync.json").write_text(
        __import__("json").dumps(
            {"networks": counts, "synced_at": datetime.now(UTC).isoformat()},
            indent=2,
        ),
        encoding="utf-8",
    )
    return counts
