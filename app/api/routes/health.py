from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

UTC = timezone.utc

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.files import report_path
from app.db.session import connect, init_db
from app.services.scheduler_service import scheduler_state
from app.services.source_health_service import get_source_health

router = APIRouter()


def _ingest_age_minutes(ingest: dict) -> float | None:
    updated = ingest.get("snapshot_updated_at")
    if not updated:
        return None
    try:
        parsed = datetime.fromisoformat(updated.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (datetime.now(UTC) - parsed).total_seconds() / 60


@router.get("/health")
def health() -> dict:
    init_db()
    db_ok = False
    complaint_count = 0
    try:
        with connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM complaints").fetchone()
            complaint_count = int(row["c"] or 0)
            db_ok = True
    except Exception as exc:
        return {
            "status": "degraded",
            "service": "trafficmy",
            "db_ok": False,
            "error": str(exc),
            "scheduler": scheduler_state(),
        }

    ingest: dict = {}
    ingest_path = report_path("latest_ingest_summary.json")
    if ingest_path.exists():
        try:
            ingest = json.loads(ingest_path.read_text(encoding="utf-8"))
            ingest["snapshot_updated_at"] = datetime.fromtimestamp(
                ingest_path.stat().st_mtime, tz=UTC
            ).isoformat()
        except json.JSONDecodeError:
            ingest = {}

    age_minutes = _ingest_age_minutes(ingest)
    stale = age_minutes is None or age_minutes > settings.stale_after_minutes

    sources = get_source_health()
    alerts = [
        f"{src['source']}: {src['consecutive_empty_runs']} consecutive empty/failed ingests — {src.get('error') or 'no reason logged'}"
        for src in sources
        if src.get("needs_attention")
    ]
    status = "ok" if db_ok and not stale and not alerts else "degraded"

    threads_count = int(ingest.get("threads", 0))
    threads_rows_last_ingest = threads_count

    return {
        "status": status,
        "service": "trafficmy",
        "db_ok": db_ok,
        "complaint_count": complaint_count,
        "threads_rows_last_ingest": threads_rows_last_ingest,
        "threads_count": threads_rows_last_ingest,
        "primary_signal": "threads",
        "ingest_age_minutes": round(age_minutes, 1) if age_minutes is not None else None,
        "stale_after_minutes": settings.stale_after_minutes,
        "is_stale": stale,
        "alerts": alerts,
        "last_ingest": ingest,
        "scheduler": scheduler_state(),
        "sources": sources,
    }


@router.get("/health/live")
def live() -> JSONResponse:
    try:
        init_db()
        with connect() as conn:
            conn.execute("SELECT 1").fetchone()
    except Exception as exc:
        return JSONResponse(
            status_code=503,
            content={"status": "down", "service": "trafficmy", "error": str(exc)},
        )
    state = scheduler_state()
    process_ok = not settings.auto_refresh_enabled or state.get("thread_alive", False)
    return JSONResponse(
        status_code=200 if process_ok else 503,
        content={"status": "ok" if process_ok else "degraded", "service": "trafficmy", "scheduler": state},
    )


@router.get("/health/ready")
def ready() -> JSONResponse:
    payload = health()
    ok = payload.get("status") == "ok"
    return JSONResponse(status_code=200 if ok else 503, content=payload)
