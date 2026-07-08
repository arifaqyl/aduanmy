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
    TRANSPORT_ACTIONABLE_IMPACT_TERMS,
    TRANSPORT_CHATTER_PATTERNS,
    TRANSPORT_CONCRETE_CAUSE_TERMS,
    TRANSPORT_CONDITIONAL_LINE_RE,
    TRANSPORT_FUTURE_INCIDENT_RE,
    TRANSPORT_FUTURE_WAIT_RE,
    TRANSPORT_HYPOTHETICAL_TERMS,
    TRANSPORT_LIVE_CONTEXT_TERMS,
    TRANSPORT_PLANNING_DEBATE_RE,
    TRANSPORT_PLANNING_OPINION_TERMS,
    TRANSPORT_PRESENT_ACTIVE_TERMS,
    TRANSPORT_SARCASTIC_WAIT_RE,
    TRANSPORT_STRONG_INCIDENT_TERMS,
    TRANSPORT_TODAY_RIDER_TERMS,
    TRANSPORT_USELESS_OPINION_TERMS,
    TRANSPORT_WEAK_INCIDENT_TERMS,
    detect_severity,
    extract_bus_route,
    extract_entity,
    extract_location,
    has_strict_malaysia_transport_anchor,
    transport_incident_signal_ok,
    transport_non_live_opinion,
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


# ---------------------------------------------------------------------------
# New ops helpers
# ---------------------------------------------------------------------------


def _is_suspicious_accepted(text: str) -> bool:
    """Return True when an accepted row has weak signals (question, chatter, opinion)."""
    low = (text or "").lower()
    if "?" in low:
        return True
    if any(re.search(p, low, re.I) for p in TRANSPORT_CHATTER_PATTERNS):
        return True
    if any(term in low for term in TRANSPORT_USELESS_OPINION_TERMS):
        return True
    if any(term in low for term in TRANSPORT_PLANNING_OPINION_TERMS):
        return True
    if TRANSPORT_SARCASTIC_WAIT_RE.search(low):
        return True
    if TRANSPORT_FUTURE_INCIDENT_RE.search(low):
        return True
    if TRANSPORT_PLANNING_DEBATE_RE.search(low):
        return True
    # Threads scrape chrome without strong measured wait — often opinion blobs.
    if re.search(r"\b[a-z0-9_\.]{3,24}\s+\d{1,2}[hm]\b", low) and not re.search(
        r"\b\d{1,3}\s*(?:min|mins|minute|minutes|minit)\b", low
    ):
        return True
    return False


def dashboard_snapshot(
    *,
    prod_health_url: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Combined dashboard: session, collector, recent runs, QA sample, remote health."""
    qa = qa_threads_rows(recent_threads_complaints(limit=40, db_path=db_path))
    accepted = qa.get("accepted", [])
    accepted_sample = accepted[:3]
    suspicious_sample = [row for row in accepted if _is_suspicious_accepted(row.get("preview", ""))][:3]

    snapshot: dict[str, Any] = {
        "session": session_panel(),
        "collector": threads_source_health(),
        "runs": recent_threads_runs(limit=5),
        "accepted_sample": accepted_sample,
        "suspicious_sample": suspicious_sample,
    }
    if prod_health_url:
        try:
            snapshot["remote_health"] = fetch_remote_health(prod_health_url)
        except Exception as exc:
            snapshot["remote_health"] = {"error": str(exc)}
    return snapshot


def _matched_terms(low: str, terms: list[str]) -> list[str]:
    """Return which terms from *terms* appear in *low*."""
    return [t for t in terms if t in low]


def _matched_patterns(low: str, patterns: list[str]) -> list[str]:
    """Return which regex pattern strings from *patterns* match *low*."""
    return [p for p in patterns if re.search(p, low, re.I)]


def _matched_re(low: str, name: str, compiled: re.Pattern[str]) -> list[str]:
    """Return [name] if *compiled* matches *low*, else []."""
    return [name] if compiled.search(low) else []


def explain_rider_gate_verbose(text: str, *, entity_hint: str = "") -> dict[str, Any]:
    """Like explain_rider_gate but each step also includes ``matched_terms``."""
    entity = entity_hint or extract_entity(text, "transport") or ""
    location = extract_location(text) or ""
    low = (text or "").lower()
    steps: list[dict[str, Any]] = []

    # --- non_live_opinion ---------------------------------------------------
    non_live_matches: list[str] = []
    non_live_matches.extend(_matched_re(low, "TRANSPORT_SARCASTIC_WAIT_RE", TRANSPORT_SARCASTIC_WAIT_RE))
    non_live_matches.extend(_matched_re(low, "TRANSPORT_FUTURE_INCIDENT_RE", TRANSPORT_FUTURE_INCIDENT_RE))
    non_live_matches.extend(_matched_re(low, "TRANSPORT_FUTURE_WAIT_RE", TRANSPORT_FUTURE_WAIT_RE))
    non_live_matches.extend(_matched_re(low, "TRANSPORT_PLANNING_DEBATE_RE", TRANSPORT_PLANNING_DEBATE_RE))
    non_live_matches.extend(_matched_re(low, "TRANSPORT_CONDITIONAL_LINE_RE", TRANSPORT_CONDITIONAL_LINE_RE))
    non_live_matches.extend(_matched_terms(low, TRANSPORT_PLANNING_OPINION_TERMS))
    non_live_matches.extend(_matched_terms(low, TRANSPORT_USELESS_OPINION_TERMS))
    non_live_matches.extend(_matched_terms(low, TRANSPORT_HYPOTHETICAL_TERMS))
    non_live_hit = transport_non_live_opinion(text)
    steps.append({
        "gate": "non_live_opinion",
        "pass": str(not non_live_hit).lower(),
        "detail": "reject prediction / planning / sarcasm",
        "matched_terms": non_live_matches,
    })
    if non_live_hit:
        return _gate_result_verbose(text, entity, location, False, steps)

    # --- transport_incident_signal_ok ---------------------------------------
    incident_ok = transport_incident_signal_ok(text, entity)
    incident_matches: list[str] = []
    incident_matches.extend(_matched_terms(low, TRANSPORT_STRONG_INCIDENT_TERMS))
    incident_matches.extend(_matched_terms(low, TRANSPORT_WEAK_INCIDENT_TERMS))
    steps.append({
        "gate": "transport_incident_signal_ok",
        "pass": str(incident_ok).lower(),
        "detail": "mentions transport complaint / delay / disruption signal",
        "matched_terms": incident_matches,
    })
    if not incident_ok:
        return _gate_result_verbose(text, entity, location, False, steps)

    # --- malaysia_transport_anchor ------------------------------------------
    anchor_ok = has_strict_malaysia_transport_anchor(text, entity=entity, location=location)
    steps.append({
        "gate": "malaysia_transport_anchor",
        "pass": str(anchor_ok).lower(),
        "detail": "Malaysia transport entity/location anchor",
        "matched_terms": [t for t in [entity, location] if t],
    })
    if not anchor_ok:
        return _gate_result_verbose(text, entity, location, False, steps)

    # --- today_context ------------------------------------------------------
    today_ok = transport_rider_today_context_ok(text)
    steps.append({
        "gate": "today_context",
        "pass": str(today_ok).lower(),
        "detail": "reads like same-day rider experience",
        "matched_terms": _matched_terms(low, TRANSPORT_TODAY_RIDER_TERMS),
    })

    # --- rider_signal_worthwhile --------------------------------------------
    worthwhile = transport_rider_signal_worthwhile(text, entity)
    rider_matches: list[str] = []
    rider_matches.extend(_matched_patterns(low, TRANSPORT_CHATTER_PATTERNS))
    rider_matches.extend(_matched_terms(low, TRANSPORT_CONCRETE_CAUSE_TERMS))
    rider_matches.extend(_matched_terms(low, TRANSPORT_ACTIONABLE_IMPACT_TERMS))
    rider_matches.extend(_matched_terms(low, TRANSPORT_PRESENT_ACTIVE_TERMS))
    rider_matches.extend(_matched_terms(low, TRANSPORT_LIVE_CONTEXT_TERMS))
    steps.append({
        "gate": "rider_signal_worthwhile",
        "pass": str(worthwhile).lower(),
        "detail": "accepted by strict rider gate" if worthwhile else _heuristic_hint(text, low),
        "matched_terms": rider_matches,
    })

    return _gate_result_verbose(text, entity, location, worthwhile, steps)


def _gate_result_verbose(
    text: str,
    entity: str,
    location: str,
    accepted: bool,
    steps: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "accepted": accepted,
        "entity": entity or extract_bus_route(text) or "",
        "location": location,
        "preview": (text or "").replace("\n", " ")[:240],
        "steps": steps,
    }


def add_eval_case(
    text: str,
    *,
    expected: bool,
    note: str = "",
    entity_hint: str = "",
    cases_path: Path | None = None,
) -> dict[str, Any]:
    """Append a labelled eval case for the rider-signal gate."""
    path = cases_path or Path(__file__).resolve().parents[2] / "tests" / "eval" / "rider_signal_cases.json"
    cases: list[dict[str, Any]] = []
    if path.is_file():
        cases = json.loads(path.read_text(encoding="utf-8"))

    if any(c.get("text") == text for c in cases):
        return {"added": False, "reason": "duplicate"}

    case: dict[str, Any] = {"text": text, "expected": expected}
    if entity_hint:
        case["entity_hint"] = entity_hint
    if note:
        case["note"] = note
    cases.append(case)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"added": True, "total_cases": len(cases)}


def run_eval_cases(*, cases_path: Path | None = None) -> dict[str, Any]:
    """Run the rider-signal eval harness inline and return metrics."""
    path = cases_path or Path(__file__).resolve().parents[2] / "tests" / "eval" / "rider_signal_cases.json"
    cases: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))

    results: list[dict[str, Any]] = []
    for case in cases:
        actual = transport_rider_signal_worthwhile(case["text"], case.get("entity_hint", ""))
        results.append({**case, "actual": actual, "pass": actual == case["expected"]})

    total = len(results)
    passed = sum(r["pass"] for r in results)
    tp = sum(1 for r in results if r["expected"] and r["actual"])
    fp = sum(1 for r in results if not r["expected"] and r["actual"])
    fn = sum(1 for r in results if r["expected"] and not r["actual"])

    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")

    failures = [
        {"text": r["text"], "expected": r["expected"], "actual": r["actual"], "note": r.get("note", "")}
        for r in results
        if not r["pass"]
    ]

    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "accuracy": passed / total if total else float("nan"),
        "precision": precision,
        "recall": recall,
        "failures": failures,
    }


def impact_preview(db_path: Path | None = None) -> list[dict[str, Any]]:
    """Per-entity breakdown: how many rows exist vs. would be pruned by current gates."""
    rows = recent_threads_complaints(limit=200, db_path=db_path)
    entities: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        text = row.get("raw_text") or ""
        entity = extract_entity(text, "transport") or row.get("entity") or "(unknown)"
        entities.setdefault(entity, []).append(row)

    out: list[dict[str, Any]] = []
    for entity, entity_rows in sorted(entities.items()):
        total_rows = len(entity_rows)
        would_prune = 0
        remaining_texts: list[str] = []
        for row in entity_rows:
            text = row.get("raw_text") or ""
            ent = entity
            if not (transport_incident_signal_ok(text, ent) and transport_rider_signal_worthwhile(text, ent)):
                would_prune += 1
            else:
                remaining_texts.append(text)
        remaining_rows = total_rows - would_prune

        if remaining_texts:
            combined = " ".join(remaining_texts)
            projected_severity = detect_severity(combined)
        else:
            projected_severity = "none"

        all_texts = " ".join(row.get("raw_text") or "" for row in entity_rows)
        current_severity = detect_severity(all_texts)

        out.append({
            "entity": entity,
            "total_rows": total_rows,
            "would_prune": would_prune,
            "remaining_rows": remaining_rows,
            "current_severity": current_severity,
            "projected_severity": projected_severity,
        })
    return out


def prune_candidates(db_path: Path) -> list[dict[str, Any]]:
    """Return detailed info for each transport row that would be pruned by current gates."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, source_platform, raw_text, entity, category
            FROM complaints
            WHERE category = 'transport'
              AND source_platform IN ('threads', 'reddit', 'rss', 'x', 'gtfs_rt')
            """,
        ).fetchall()
    finally:
        conn.close()

    out: list[dict[str, Any]] = []
    for row in rows:
        text = row["raw_text"] or ""
        entity = row["entity"] or ""
        source = row["source_platform"]

        if source == "gtfs_rt":
            out.append({
                "id": row["id"],
                "entity": entity,
                "preview": text.replace("\n", " ")[:120],
                "reason": "gtfs_rt source (always pruned)",
            })
            continue

        if not transport_incident_signal_ok(text, entity):
            out.append({
                "id": row["id"],
                "entity": entity,
                "preview": text.replace("\n", " ")[:120],
                "reason": "failed transport_incident_signal_ok",
            })
            continue

        if not transport_rider_signal_worthwhile(text, entity):
            out.append({
                "id": row["id"],
                "entity": entity,
                "preview": text.replace("\n", " ")[:120],
                "reason": "failed transport_rider_signal_worthwhile",
            })
    return out


def export_ops_report(
    *,
    prod_health_url: str | None = None,
    db_path: Path | None = None,
    out_path: Path | None = None,
) -> Path:
    """Write a JSON ops report for vault/archive (no secrets)."""
    root = Path(__file__).resolve().parents[2]
    path = out_path or (root / "output" / "threads_terminal_report.json")
    path.parent.mkdir(parents=True, exist_ok=True)

    qa = qa_threads_rows(recent_threads_complaints(limit=80, db_path=db_path))
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "dashboard": dashboard_snapshot(prod_health_url=prod_health_url, db_path=db_path),
        "qa": {
            "total": qa.get("total"),
            "accepted_count": qa.get("accepted_count"),
            "rejected_count": qa.get("rejected_count"),
            "accepted": qa.get("accepted"),
            "rejected": qa.get("rejected"),
        },
        "reject_histogram": reject_reason_counts(recent_threads_complaints(limit=100, db_path=db_path)),
        "impact": impact_preview(db_path=db_path),
        "eval": run_eval_cases(),
    }
    if db_path:
        report["prune_candidates"] = prune_candidates(db_path)

    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path

