from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from app.core.files import report_path
from app.db.session import connect, init_db
from app.services.incident_service import list_clusters
from app.services.scoring_service import score_categories


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=UTC)
        return parsed
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S",):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


def _latest_ingest_summary() -> dict:
    path = report_path("latest_ingest_summary.json")
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    payload["snapshot_file"] = str(path)
    payload["snapshot_updated_at"] = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    return payload


def get_trafficmy_status(*, stale_after_minutes: int = 180) -> dict:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS complaint_count,
                   MAX(created_at) AS latest_created_at,
                   MAX(inserted_at) AS latest_inserted_at
            FROM complaints
            WHERE source_platform != 'official'
            """
        ).fetchone()

    latest_created_at = row["latest_created_at"] if row else None
    latest_inserted_at = row["latest_inserted_at"] if row else None
    latest_signal = _parse_dt(latest_created_at)
    latest_ingest = _parse_dt(latest_inserted_at)
    latest_observed = latest_signal or latest_ingest
    now = datetime.now(UTC)
    is_stale = True if latest_observed is None else latest_observed < now - timedelta(minutes=stale_after_minutes)
    leader = next((item for item in score_categories() if item["category"] == "transport"), None)

    return {
        "product": "TrafficMY",
        "freshness": {
            "latest_created_at": latest_created_at,
            "latest_inserted_at": latest_inserted_at,
            "freshness_basis": "created_at" if latest_signal else "inserted_at",
            "stale_after_minutes": stale_after_minutes,
            "is_stale": is_stale,
        },
        "totals": {
            "complaints": int(row["complaint_count"] or 0) if row else 0,
            "transport_clusters": len(list_clusters(category="transport")),
        },
        "ingest": _latest_ingest_summary(),
        "top_wedge": leader,
    }
