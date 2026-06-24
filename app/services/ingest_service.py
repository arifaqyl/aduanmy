from __future__ import annotations

import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.collectors.official.client import collect_official_sample
from app.collectors.reddit.client import collect_reddit_sample
from app.collectors.threads.client import collect_threads_sample
from app.collectors.x.client import collect_x_sample
from app.core.files import raw_path, report_path
from app.db.session import init_db, reset_complaints, upsert_complaints
from app.pipeline.dedup import dedup_key
from app.pipeline.extract import category_signal_ok, extract_entity, extract_issue_key, extract_stub, is_complaint_signal
from app.pipeline.normalize import normalize_text
from app.schemas.complaint import ComplaintSchema


def _fallback_entity(row: dict, category: str, entity: str) -> str:
    if entity:
        return entity
    handle = (row.get("author_handle") or "").lower()
    if category == "transport" and handle in {"askrapidkl", "myrapidkl"}:
        return "RapidKL"
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
            "kelewatan",
            "gangguan",
            "disruption",
            "incident",
            "kemas kini",
            "line update",
            "service alert",
            "derail",
            "technical fault",
            "fire alarm",
        ]
        return bool((entity or location) and any(term in low for term in incident_terms))

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


def collect_all() -> dict[str, list[dict]]:
    collectors = {
        "threads": collect_threads_sample,
        "reddit": collect_reddit_sample,
        "x": collect_x_sample,
        "official": collect_official_sample,
    }
    results: dict[str, list[dict]] = {name: [] for name in collectors}
    with ThreadPoolExecutor(max_workers=len(collectors)) as executor:
        future_map = {executor.submit(func): name for name, func in collectors.items()}
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                results[name] = future.result()
            except Exception:
                results[name] = []
    return results


def collect_all_with_timings() -> tuple[dict[str, list[dict]], dict[str, float]]:
    collectors = {
        "threads": collect_threads_sample,
        "reddit": collect_reddit_sample,
        "x": collect_x_sample,
        "official": collect_official_sample,
    }
    results: dict[str, list[dict]] = {name: [] for name in collectors}
    timings: dict[str, float] = {}
    started_at: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=len(collectors)) as executor:
        future_map = {}
        for name, func in collectors.items():
            started_at[name] = time.perf_counter()
            future_map[executor.submit(func)] = name
        for future in as_completed(future_map):
            name = future_map[future]
            timings[name] = round(time.perf_counter() - started_at[name], 2)
            try:
                results[name] = future.result()
            except Exception:
                results[name] = []
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
            if row["source_platform"] != "official" and not is_complaint_signal(normalized_text):
                continue
            extracted = extract_stub(normalized_text)
            category = row.get("seed_category", "") or extracted["category"]
            entity = extract_entity(normalized_text, category)
            entity = _fallback_entity(row, category, entity)
            location = extracted["location"]
            issue_key = extract_issue_key(normalized_text, category)
            severity = "low" if row["source_platform"] == "official" else extracted["severity"]
            if row["source_platform"] != "official" and not category and not entity:
                continue
            if row["source_platform"] == "official":
                if not _official_grounding_ok(row, normalized_text, category, entity, location):
                    continue
            else:
                if category and not category_signal_ok(normalized_text, category, entity):
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
                    source_platform=row["source_platform"],
                    post_id=row["post_id"],
                    url=row["url"],
                    author_handle=row["author_handle"],
                    created_at=row.get("created_at", ""),
                    raw_text=row["raw_text"],
                    normalized_text=normalized_text,
                    detected_language_mix=extracted["detected_language_mix"],
                    category=category or "uncategorized",
                    subcategory="",
                    entity=entity,
                    location=location,
                    severity=severity,
                    confidence=0.5 if category else 0.2,
                    engagement="",
                    cluster_id=build_cluster_id(category, entity, location, issue_key, row["source_platform"]),
                )
            )
    return out


def run_ingest() -> dict[str, int]:
    init_db()
    reset_complaints()
    collected, timings = collect_all_with_timings()
    raw_file = raw_path("latest_sample.json")
    raw_file.write_text(json.dumps(collected, indent=2, ensure_ascii=False), encoding="utf-8")
    rows = transform_rows(collected)
    written = upsert_complaints(rows)
    category_counts = Counter(row.category or "uncategorized" for row in rows)
    report = {
        "written": written,
        "threads": len(collected["threads"]),
        "reddit": len(collected["reddit"]),
        "x": len(collected["x"]),
        "official": len(collected["official"]),
        "timings": timings,
        "categories": dict(category_counts),
    }
    report_path("latest_ingest_summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return report
