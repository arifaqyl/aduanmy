from __future__ import annotations

import json
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, wait
from datetime import UTC, datetime

from app.collectors.gtfs.client import collect_gtfs_sample
from app.collectors.official.client import collect_official_sample
from app.collectors.reddit.client import collect_reddit_sample
from app.collectors.rss.client import collect_rss_sample
from app.collectors.threads.client import collect_threads_sample
from app.collectors.x.client import collect_x_sample
from app.core.config import settings
from app.core.files import raw_path, report_path, write_json_atomic
from app.core.freshness import is_myt_peak_hour, parse_dt
from app.db.session import (
    connect,
    init_db,
    latest_collector_run,
    prune_old_complaints,
    record_collector_runs,
    upsert_complaints,
)
from app.pipeline.bus_alerts import classify_transport_mode, is_mass_bus_alert, is_rail_line_alert, parse_myrapid_official
from app.pipeline.dedup import dedup_key
from app.core.freshness import is_inside_myt_today
from app.pipeline.extract import (
    category_signal_ok,
    extract_bus_route,
    extract_entity,
    extract_issue_key,
    extract_stub,
    is_complaint_signal,
    transport_incident_signal_ok,
    transport_line_info_signal_ok,
    transport_rider_signal_worthwhile,
)
from app.pipeline.geo import infer_state
from app.pipeline.normalize import normalize_text
from app.schemas.complaint import ComplaintSchema


def _fallback_entity(row: dict, category: str, entity: str) -> str:
    if entity:
        return entity
    handle = (row.get("author_handle") or "").lower()
    if category == "transport" and handle in {"askrapidkl", "myrapidkl"}:
        return "RapidKL"
    if category == "transport" and handle in {"ktmb", "ktm_berhad", "ktmb_official"}:
        return "KTM"
    return entity


def _official_grounding_ok(row: dict, normalized_text: str, category: str, entity: str, location: str) -> bool:
    low = normalized_text.lower()
    handle = (row.get("author_handle") or "").lower()

    if "open data" in low and not any(
        token in low
        for token in [
            "service outage",
            "planned maintenance",
            "gangguan",
            "kelewatan",
            "line update",
            "warning",
            "banjir",
        ]
    ):
        return False

    if category == "transport":
        incident_terms = [
            "delay",
            "lambat",
            "gangguan",
            "disruption",
            "incident",
            "kemas kini",
            "line update",
            "service alert",
            "derail",
            "technical fault",
            "fire alarm",
            "terjejas",
            "kekerapan",
        ]
        has_target = bool(
            entity
            or location
            or is_mass_bus_alert(low)
            or is_rail_line_alert(low)
            or handle.startswith("official:myrapid")
        )
        return bool(has_target and any(term in low for term in incident_terms))

    if category == "telco_internet":
        return bool(
            entity
            and any(
                term in low
                for term in [
                    "service outage",
                    "planned maintenance",
                    "faulty network",
                    "service interruptions",
                    "interruption",
                    "outage",
                ]
            )
        )

    if category == "gov_portals":
        return any(
            term in low
            for term in [
                "portal down",
                "system down",
                "session expired",
                "login error",
                "maintenance",
                "cannot login",
                "tak boleh",
                "error",
            ]
        )

    if category == "flood_weather":
        return any(
            term in low
            for term in [
                "warning",
                "amaran",
                "banjir",
                "flood",
                "road closure",
                "jalan tutup",
                "hujan lebat",
            ]
        ) and "open data" not in low

    return False


def build_cluster_id(category: str, entity: str, location: str, issue_key: str, source_platform: str) -> str:
    base = category or "uncategorized"
    parts = [base]
    if entity:
        parts.append(entity)
    if location:
        parts.append(location)
    if issue_key:
        parts.append(issue_key)
    if len(parts) > 1:
        return ":".join(parts)
    return f"{base}:{source_platform}"


def _collectors() -> dict:
    return {
        "threads": collect_threads_sample,
        "reddit": collect_reddit_sample,
        "x": collect_x_sample,
        "official": collect_official_sample,
        "rss": collect_rss_sample,
        "gtfs": collect_gtfs_sample,
    }


# Hard caps so a hung Playwright Chromium cannot freeze the whole ingest + scheduler.
COLLECTOR_HARD_TIMEOUT_SECONDS = {
    "threads": 240,
    "official": 90,
    "rss": 60,
    "reddit": 90,
    "x": 90,
    "gtfs": 45,
}


def collect_all() -> dict[str, list[dict]]:
    results, _timings, _runs = collect_all_detailed(respect_cadence=False)
    return results


def _collector_due(name: str, *, respect_cadence: bool) -> tuple[bool, str]:
    if name == "gtfs" and not settings.gtfs_anomaly_enabled:
        return False, "reference_only"
    if name == "x" and not settings.x_auto_collect_enabled:
        return False, "disabled_until_authenticated"
    if not respect_cadence:
        return True, ""
    # When Threads is empty/failed, force Reddit regardless of cadence so the board
    # is not blind during a starved primary lane.
    if name == "reddit":
        threads_prev = latest_collector_run("threads", include_paused=False)
        if threads_prev and threads_prev.get("status") in {"empty", "failed"}:
            return True, ""
    # Reddit is the fallback lane when Threads goes quiet — run it more often during
    # KL commute rush hours so a stalled Threads session doesn't leave the pulse blind.
    reddit_interval = (
        min(settings.reddit_min_interval_seconds, 1800)
        if is_myt_peak_hour()
        else settings.reddit_min_interval_seconds
    )
    minimum = {
        "reddit": reddit_interval,
        "x": settings.x_min_interval_seconds,
    }.get(name, 0)
    if minimum <= 0:
        return True, ""
    previous = latest_collector_run(name, include_paused=False)
    finished_at = parse_dt(previous.get("finished_at")) if previous else None
    if finished_at is None:
        return True, ""
    age_seconds = (datetime.now(UTC) - finished_at).total_seconds()
    if age_seconds < minimum:
        return False, f"cadence:{minimum}s"
    return True, ""


def collect_all_detailed(
    *, respect_cadence: bool = False
) -> tuple[dict[str, list[dict]], dict[str, float], list[dict]]:
    collectors = _collectors()
    results: dict[str, list[dict]] = {name: [] for name in collectors}
    timings: dict[str, float] = {}
    started_at: dict[str, float] = {}
    started_iso: dict[str, str] = {}
    runs: list[dict] = []
    executor = ThreadPoolExecutor(max_workers=len(collectors))
    try:
        future_map = {}
        for name, func in collectors.items():
            due, reason = _collector_due(name, respect_cadence=respect_cadence)
            if not due:
                now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")
                runs.append(
                    {
                        "source": name,
                        "started_at": now_iso,
                        "finished_at": now_iso,
                        "status": "paused",
                        "row_count": 0,
                        "duration_seconds": 0,
                        "error": reason,
                    }
                )
                timings[name] = 0.0
                continue
            started_at[name] = time.perf_counter()
            started_iso[name] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
            future_map[executor.submit(func)] = name
        pending = set(future_map)
        while pending:
            done, pending = wait_done(pending, timeout=1.0)
            for future in done:
                name = future_map[future]
                hard_timeout = COLLECTOR_HARD_TIMEOUT_SECONDS.get(name, 90)
                elapsed = time.perf_counter() - started_at[name]
                remaining = max(0.1, hard_timeout - elapsed)
                error = ""
                try:
                    results[name] = future.result(timeout=remaining)
                    status = "healthy" if results[name] else "empty"
                except FuturesTimeoutError:
                    results[name] = []
                    status = "failed"
                    error = f"timeout:{hard_timeout}s"
                    future.cancel()
                except Exception as exc:
                    results[name] = []
                    status = "failed"
                    error = f"{type(exc).__name__}: {exc}"
                duration = round(time.perf_counter() - started_at[name], 2)
                timings[name] = duration
                if name == "threads" and status != "healthy":
                    from app.collectors.threads.client import get_threads_diagnostics

                    diag = get_threads_diagnostics()
                    reasons = diag.get("reasons") or []
                    bits = list(reasons[:4])
                    rejected_today = diag.get("rejected_not_today")
                    rejected_signal = diag.get("rejected_weak_rider_signal")
                    if rejected_today:
                        bits.append(f"rejected_not_today={rejected_today}")
                    if rejected_signal:
                        bits.append(f"rejected_weak_rider_signal={rejected_signal}")
                    if bits:
                        error = (error + " | " if error else "") + "; ".join(bits)
                runs.append(
                    {
                        "source": name,
                        "started_at": started_iso[name],
                        "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        "status": status,
                        "row_count": len(results[name]),
                        "duration_seconds": duration,
                        "error": error,
                    }
                )
            # Sweep long-running futures that never completed a tick.
            still = set()
            for future in pending:
                name = future_map[future]
                hard_timeout = COLLECTOR_HARD_TIMEOUT_SECONDS.get(name, 90)
                elapsed = time.perf_counter() - started_at[name]
                if elapsed < hard_timeout:
                    still.add(future)
                    continue
                results[name] = []
                timings[name] = round(elapsed, 2)
                future.cancel()
                error = f"timeout:{hard_timeout}s"
                if name == "threads":
                    from app.collectors.threads.client import get_threads_diagnostics

                    diag = get_threads_diagnostics()
                    reasons = diag.get("reasons") or []
                    bits = list(reasons[:4])
                    rejected_today = diag.get("rejected_not_today")
                    rejected_signal = diag.get("rejected_weak_rider_signal")
                    if rejected_today:
                        bits.append(f"rejected_not_today={rejected_today}")
                    if rejected_signal:
                        bits.append(f"rejected_weak_rider_signal={rejected_signal}")
                    if bits:
                        error = error + " | " + "; ".join(bits)
                runs.append(
                    {
                        "source": name,
                        "started_at": started_iso[name],
                        "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                        "status": "failed",
                        "row_count": 0,
                        "duration_seconds": round(elapsed, 2),
                        "error": error,
                    }
                )
            pending = still
    finally:
        # Never block forever on a hung Playwright process.
        executor.shutdown(wait=False, cancel_futures=True)
    return results, timings, sorted(runs, key=lambda item: item["source"])


def wait_done(futures: set, timeout: float):
    """Thin wrapper so tests can stub wait behavior if needed."""
    done, not_done = wait(futures, timeout=timeout, return_when=FIRST_COMPLETED)
    return done, not_done


def collect_all_with_timings() -> tuple[dict[str, list[dict]], dict[str, float]]:
    results, timings, _runs = collect_all_detailed()
    return results, timings


def transform_rows(collected: dict[str, list[dict]]) -> list[ComplaintSchema]:
    seen: set[str] = set()
    out: list[ComplaintSchema] = []
    for rows in collected.values():
        for row in rows:
            key = dedup_key(row["source_platform"], row["post_id"])
            if key in seen:
                continue
            seen.add(key)
            normalized_text = normalize_text(row["raw_text"])
            platform = row["source_platform"]
            if platform not in {"official", "rss", "gtfs_rt"} and not is_complaint_signal(normalized_text):
                if not transport_line_info_signal_ok(normalized_text):
                    continue
            extracted = extract_stub(normalized_text)
            category = row.get("seed_category", "") or extracted["category"]
            entity = extract_bus_route(normalized_text) or extract_entity(normalized_text, category)
            entity = _fallback_entity(row, category, entity)
            location = extracted["location"]
            issue_key = extract_issue_key(normalized_text, category)
            subcategory = row.get("subcategory", "")
            severity = extracted["severity"]

            if platform == "official" and category == "transport":
                parsed = parse_myrapid_official(row["raw_text"])
                entity = parsed.get("entity") or entity
                subcategory = parsed.get("subcategory") or subcategory
                if parsed.get("severity"):
                    severity = parsed["severity"]

            if platform == "gtfs_rt":
                entity = row.get("entity") or entity
                subcategory = row.get("subcategory", "bus")
                severity = row.get("severity", "medium")

            state = row.get("state") or infer_state(
                text=normalized_text,
                location=location,
                entity=entity,
                category=category,
            )
            subcategory = subcategory or classify_transport_mode(
                text=normalized_text,
                entity=entity,
                subcategory=subcategory,
            )
            if category == "transport" and subcategory != "line_info":
                if transport_line_info_signal_ok(normalized_text, entity) and not transport_incident_signal_ok(
                    normalized_text, entity
                ):
                    subcategory = "line_info"
                    severity = "low"

            if platform == "official":
                severity = "low" if not parse_myrapid_official(row["raw_text"]).get("severity") else severity

            if platform != "official" and not category and not entity:
                continue
            if platform == "official":
                if not _official_grounding_ok(row, normalized_text, category, entity, location):
                    continue
            elif platform == "gtfs_rt":
                if not entity:
                    continue
            else:
                if subcategory == "line_info":
                    if not transport_line_info_signal_ok(normalized_text, entity):
                        continue
                elif category and not category_signal_ok(normalized_text, category, entity):
                    continue
                if (
                    category == "transport"
                    and subcategory != "line_info"
                    and platform in {"reddit", "rss", "threads"}
                ):
                    if not transport_rider_signal_worthwhile(normalized_text, entity):
                        continue
                    created_at = row.get("created_at", "")
                    if created_at and not is_inside_myt_today(created_at):
                        continue
                if category in {"banking_payments", "gov_portals", "telco_internet"} and not entity:
                    continue
                if category == "flood_weather" and not any(
                    token in normalized_text
                    for token in ["banjir", "flood", "road closure", "jalan tutup", "hujan lebat"]
                ):
                    continue
            out.append(
                ComplaintSchema(
                    source_platform=platform,
                    post_id=row["post_id"],
                    url=row["url"],
                    author_handle=row["author_handle"],
                    created_at=row.get("created_at", ""),
                    raw_text=row["raw_text"],
                    normalized_text=normalized_text,
                    detected_language_mix=extracted["detected_language_mix"],
                    category=category or "uncategorized",
                    subcategory=subcategory,
                    entity=entity,
                    location=location,
                    state=state,
                    severity=severity,
                    confidence=0.65 if platform == "gtfs_rt" else (0.5 if category else 0.2),
                    engagement="",
                    cluster_id=build_cluster_id(category, entity, location, issue_key, platform),
                )
            )
    return out


def prune_gtfs_rt_complaints() -> int:
    """GTFS-RT anomaly rows are reference telemetry, not rider incidents."""
    init_db()
    with connect() as conn:
        cur = conn.execute("DELETE FROM complaints WHERE source_platform = 'gtfs_rt'")
        return int(cur.rowcount or 0)


def prune_rejected_social_complaints() -> int:
    """Remove social rows that no longer pass TrafficMY's live rider-signal gate."""
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT id, source_platform, category, entity, raw_text
            FROM complaints
            WHERE source_platform IN ('threads', 'reddit', 'rss', 'x')
            """
        ).fetchall()

    rejected_ids: list[int] = []
    for row in rows:
        category = str(row["category"] or "")
        if category != "transport":
            rejected_ids.append(int(row["id"]))
            continue
        if not transport_rider_signal_worthwhile(str(row["raw_text"] or ""), str(row["entity"] or "")):
            rejected_ids.append(int(row["id"]))

    if not rejected_ids:
        return 0

    deleted = 0
    with connect() as conn:
        for start in range(0, len(rejected_ids), 500):
            batch = rejected_ids[start : start + 500]
            placeholders = ",".join("?" for _ in batch)
            cur = conn.execute(f"DELETE FROM complaints WHERE id IN ({placeholders})", batch)
            deleted += int(cur.rowcount or 0)
    return deleted


def prune_rejected_threads_complaints() -> int:
    """Backward-compatible alias."""
    return prune_rejected_social_complaints()


def run_gtfs_ingest() -> dict:
    init_db()
    from app.collectors.gtfs.anomaly import detect_route_anomalies
    from app.collectors.gtfs.static_client import sync_static_catalog

    started = time.perf_counter()
    sync_static_catalog()
    rows = detect_route_anomalies()
    transformed = transform_rows({"gtfs": rows})
    written = upsert_complaints(transformed)
    report = {
        "written": written,
        "gtfs_raw": len(rows),
        "duration_seconds": round(time.perf_counter() - started, 2),
    }
    return report


def run_ingest(*, respect_cadence: bool = False) -> dict:
    init_db()
    run_started = datetime.now(UTC)
    run_id = run_started.isoformat().replace("+00:00", "Z")
    collected, timings, source_runs = collect_all_detailed(respect_cadence=respect_cadence)
    raw_file = raw_path("latest_sample.json")
    write_json_atomic(raw_file, collected)
    rows = transform_rows(collected)
    written = upsert_complaints(rows)
    pruned = prune_old_complaints()
    gtfs_pruned = prune_gtfs_rt_complaints()
    threads_pruned = prune_rejected_social_complaints()
    category_counts = Counter(row.category or "uncategorized" for row in rows)
    state_counts = Counter(row.state for row in rows if row.state)
    mode_counts = Counter(row.subcategory for row in rows if row.subcategory)
    report = {
        "status": "degraded" if any(run["status"] == "failed" for run in source_runs) else "ok",
        "run_id": run_id,
        "started_at": run_id,
        "finished_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "duration_seconds": round((datetime.now(UTC) - run_started).total_seconds(), 2),
        "written": written,
        "pruned": pruned,
        "gtfs_pruned": gtfs_pruned,
        "threads_pruned_rejected": threads_pruned,
        "threads": len(collected["threads"]),
        "reddit": len(collected["reddit"]),
        "x": len(collected["x"]),
        "official": len(collected["official"]),
        "rss": len(collected["rss"]),
        "gtfs": len(collected["gtfs"]),
        "timings": timings,
        "categories": dict(category_counts),
        "states": dict(state_counts),
        "modes": dict(mode_counts),
        "sources": {run["source"]: run for run in source_runs},
    }
    record_collector_runs(run_id, source_runs)
    write_json_atomic(report_path("latest_ingest_summary.json"), report)
    return report
