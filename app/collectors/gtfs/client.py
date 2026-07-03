from __future__ import annotations

import os

from app.collectors.gtfs.anomaly import detect_route_anomalies
from app.collectors.gtfs.static_client import sync_static_catalog


def collect_gtfs_sample() -> list[dict]:
    if os.getenv("PYTEST_CURRENT_TEST"):
        return []
    try:
        sync_static_catalog()
    except Exception:
        pass
    try:
        return detect_route_anomalies()
    except Exception:
        return []
