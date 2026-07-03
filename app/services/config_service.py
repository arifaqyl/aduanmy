from __future__ import annotations

import json

from app.core.config import settings
from app.core.files import report_path
from app.core.freshness import LIVE_WINDOW_DAYS
from app.collectors.threads.session import session_status
from app.services.source_health_service import get_source_health

SOURCE_LANES = {
    "threads": {
        "label": "Threads",
        "role": "primary_social",
        "default_status": "active",
        "notes": "Cookie-authenticated Threads web search with public fallback",
    },
    "official": {
        "label": "Official",
        "role": "ground_truth",
        "default_status": "active",
        "notes": "MyRapid, KTMB, telco outage pages",
    },
    "gtfs": {
        "label": "GTFS-RT",
        "role": "reference_telemetry",
        "default_status": "active",
        "notes": "Optional map telemetry only; never used as incident truth",
    },
    "reddit": {
        "label": "Reddit",
        "role": "secondary_social",
        "default_status": "active",
        "notes": "old.reddit HTML search",
    },
    "rss": {
        "label": "News RSS",
        "role": "news_syndication",
        "default_status": "active",
        "notes": "Google News RSS feeds",
    },
    "x": {
        "label": "X",
        "role": "tertiary_social",
        "default_status": "dormant",
        "notes": "Paused in unattended collection until authenticated",
    },
}


def _latest_ingest_counts() -> dict[str, int]:
    path = report_path("latest_ingest_summary.json")
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        name: int(payload.get(name, 0) or 0)
        for name in SOURCE_LANES
    }


def _lane_status(name: str, count: int, run_status: str = "") -> str:
    meta = SOURCE_LANES[name]
    if name == "gtfs" and not settings.gtfs_anomaly_enabled:
        return "reference"
    if run_status == "failed":
        return "failed"
    if run_status == "empty":
        return "empty"
    if run_status == "paused":
        return "dormant" if name == "x" else "scheduled"
    if name == "x":
        return "dormant" if count == 0 else "active"
    if count > 0:
        return "active"
    if meta["default_status"] == "dormant":
        return "dormant"
    return "degraded"


def get_trafficmy_config() -> dict:
    counts = _latest_ingest_counts()
    source_runs = {item["source"]: item for item in get_source_health()}
    threads_session = session_status()
    lanes = []
    for name, meta in SOURCE_LANES.items():
        count = counts.get(name, 0)
        run = source_runs.get(name, {})
        lanes.append(
            {
                "id": name,
                "label": meta["label"],
                "role": meta["role"],
                "status": _lane_status(name, count, run.get("status", "")),
                "last_ingest_count": count,
                "notes": (
                    meta["notes"]
                    if name != "threads" or threads_session["available"]
                    else "Public Threads web search fallback; authenticated session unavailable"
                ),
                "last_checked_at": run.get("finished_at"),
                "last_nonempty_at": run.get("last_nonempty_at"),
                "duration_seconds": run.get("duration_seconds"),
                "collector_status": run.get("status", "unknown"),
            }
        )

    return {
        "product": "TrafficMY",
        "live_window_days": LIVE_WINDOW_DAYS,
        "poll_interval_seconds": settings.dashboard_poll_interval_seconds,
        "ingest_interval_seconds": settings.full_refresh_interval_seconds,
        "gtfs_ingest_interval_seconds": settings.gtfs_refresh_interval_seconds,
        "gtfs_anomaly_enabled": settings.gtfs_anomaly_enabled,
        "auto_refresh_enabled": settings.auto_refresh_enabled,
        "refresh_requires_key": bool(settings.refresh_api_key) and not settings.allow_dashboard_refresh,
        "allow_dashboard_refresh": settings.allow_dashboard_refresh,
        "manual_scrape_enabled": settings.allow_dashboard_refresh,
        "threads_authenticated_session_enabled": threads_session["available"],
        "threads_session_updated_at": threads_session["updated_at"],
        "discovery_depth": settings.discovery_depth,
        "source_lanes": lanes,
    }
