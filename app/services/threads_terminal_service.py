"""Ops helpers for Threads Terminal — session, gates, QA, collector health."""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from app.collectors.threads.client import get_threads_diagnostics
from app.collectors.threads.session import session_status
from app.core.freshness import is_inside_myt_today, parse_dt
from app.db.session import connect, init_db
from app.pipeline.extract import (
    extract_bus_route,
    extract_entity,
    extract_location,
    has_strict_malaysia_transport_anchor,
    transport_incident_signal_ok,
    transport_rider_signal_worthwhile,
    transport_rider_today_context_ok,
)
from app.services.source_health_service import CONSECUTIVE_EMPTY_ALERT_THRESHOLD, get_source_health


def explain_rider_gate(text: str, *, entity_hint: str = "") -> dict[str, Any]:
    """Step through Threads transport gates and return accept/reject reasons."""
    entity = entity_hint or extract_entity(text, "transport") or ""
    location = extract_location(text) or ""
    low = (text or "").lower()
    steps: list[dict[str, str]] = []

    incident_ok = transport_incident_signal_ok(text, entity)
    steps.append(
        {
            "gate": "transport_incident_signal_ok",
            "pass": str(incident_ok).lower(),
            "detail": "mentions transport complaint / delay / disruption signal",
        }
    )
    if not incident_ok:
        return _gate_result(text, entity, location, False, steps)

    anchor_ok = has_strict_malaysia_transport_anchor(text, entity=entity, location=location)
    steps.append(
        {
            "gate": "malaysia_transport_anchor",
            "pass": str(anchor_ok).lower(),
            "detail": "Malaysia transport entity/location anchor",
        }
    )
    if not anchor_ok:
        return _gate_result(text, entity, location, False, steps)

    steps.append(
        {
            "gate": "today_context",
            "pass": str(transport_rider_today_context_ok(text)).lower(),
            "detail": "reads like same-day rider experience (may be waived with strong evidence)",
        }
    )

    worthwhile = transport_rider_signal_worthwhile(text, entity)
    if not worthwhile:
        steps.append({"gate": "rider_signal_worthwhile", "pass": "false", "detail": _heuristic_hint(text, low)})
    else:
        steps.append({"gate": "rider_signal_worthwhile", "pass": "true", "detail": "accepted by strict rider gate"})

    return _gate_result(text, entity, location, worthwhile, steps)


def _gate_result(
    text: str,
    entity: str,
    location: str,
    accepted: bool,
    steps: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "accepted": accepted,
        "entity": entity or extract_bus_route(text) or "",
        "location": location,
        "preview": (text or "").replace("\n", " ")[:240],
        "steps": steps,
    }


def _heuristic_hint(text: str, low: str) -> str:
    if any(t in low for t in ["rasuah", "ptptn", "my selangorku", "tunggu grab"]):
        return "rejected: politics/housing/grab-wait noise"
    if "?" in low:
        return "rejected: question without observable impact"
    if re.search(r"\b(?:dah lambat|selalu sesak)\b", low):
        return "rejected: habitual gripe without today signal"
    if len(re.findall(r"\b[a-z0-9_\.]{3,24}\s+\d+[hm]\b", low)) >= 2:
        return "rejected: aggregated search preview blob"
    if not transport_rider_today_context_ok(text):
        return "rejected: missing today context and no strong cause/direct evidence"
    return "rejected: chatter or weak signal (see transport_rider_signal_worthwhile rules)"


def session_panel() -> dict[str, Any]:
    status = session_status()
    path = Path(__file__).resolve().parents[2] / "data" / "private" / "threads-session.json"
    return {
        "path": str(path),
        "available": status.get("available"),
        "updated_at": status.get("updated_at"),
        "size_bytes": path.stat().st_size if path.is_file() else 0,
    }


def threads_source_health() -> dict[str, Any] | None:
    for item in get_source_health():
        if item.get("source") == "threads":
            return item
    return None


def recent_threads_runs(*, limit: int = 12) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT run_id, started_at, finished_at, status, row_count,
                   duration_seconds, error
            FROM collector_runs
            WHERE source = 'threads'
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def recent_threads_complaints(*, limit: int = 40, db_path: Path | None = None) -> list[dict[str, Any]]:
    if db_path:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
    else:
        init_db()
        conn = connect()
    try:
        rows = conn.execute(
            """
            SELECT id, source_platform, raw_text, entity, location, created_at, inserted_at
            FROM complaints
            WHERE source_platform = 'threads' AND category = 'transport'
            ORDER BY COALESCE(created_at, inserted_at) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(row) for row in rows]


def qa_threads_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    accepted: list[dict] = []
    rejected: list[dict] = []
    for row in rows:
        text = row.get("raw_text") or ""
        entity = extract_entity(text, "transport") or row.get("entity") or ""
        created = row.get("created_at") or row.get("inserted_at")
        parsed = parse_dt(created)
        today_ok = parsed is not None and is_inside_myt_today(created)
        incident = transport_incident_signal_ok(text, entity)
        worthwhile = transport_rider_signal_worthwhile(text, entity) if incident else False
        verdict = {
            "id": row.get("id"),
            "created_at": created,
            "today_myt": today_ok,
            "entity": entity,
            "preview": text[:180].replace("\n", " "),
            "incident_ok": incident,
            "worthwhile": worthwhile,
        }
        if incident and worthwhile and today_ok:
            accepted.append(verdict)
        else:
            reason = "not today MYT" if incident and worthwhile and not today_ok else explain_rider_gate(text, entity_hint=entity)
            if isinstance(reason, dict):
                verdict["reason"] = "gate failed" if not reason.get("accepted") else "not today MYT"
                verdict["steps"] = reason.get("steps")
            else:
                verdict["reason"] = str(reason)
            rejected.append(verdict)
    return {
        "total": len(rows),
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "accepted": accepted[:12],
        "rejected": rejected[:20],
    }


def load_ingest_summary(report_dir: Path | None = None) -> dict[str, Any]:
    root = report_dir or Path(__file__).resolve().parents[2]
    path = root / "output" / "latest_ingest_summary.json"
    if not path.is_file():
        path = root / "data" / "reports" / "latest_ingest_summary.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def fetch_remote_health(base_url: str, *, timeout: float = 12.0) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/api/health"
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "TrafficMY-ThreadsTerminal/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def status_snapshot(*, prod_health_url: str | None = None) -> dict[str, Any]:
    health = threads_source_health()
    ingest = load_ingest_summary()
    snapshot: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "session": session_panel(),
        "threads_collector": health,
        "last_diagnostics": get_threads_diagnostics(),
        "ingest_summary": {
            "threads": ingest.get("threads"),
            "last_error": ingest.get("error") or ingest.get("scheduler_error"),
        },
        "alert_threshold": CONSECUTIVE_EMPTY_ALERT_THRESHOLD,
    }
    if prod_health_url:
        try:
            snapshot["remote_health"] = fetch_remote_health(prod_health_url)
        except Exception as exc:
            snapshot["remote_health_error"] = str(exc)
    return snapshot


def reject_reason_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        text = row.get("raw_text") or ""
        entity = extract_entity(text, "transport") or ""
        if transport_incident_signal_ok(text, entity) and transport_rider_signal_worthwhile(text, entity):
            continue
        explained = explain_rider_gate(text, entity_hint=entity)
        key = explained["steps"][-1]["detail"] if explained.get("steps") else "unknown"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: -item[1]))
