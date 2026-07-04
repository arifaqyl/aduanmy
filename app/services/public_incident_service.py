from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from app.core.freshness import MYT, parse_dt

_ISSUE_LABELS = {
    "delay": "delay",
    "disruption": "disruption",
    "incident": "service issue",
    "technical_fault": "technical fault",
    "crowding": "crowding",
    "outage": "outage",
    "stuck": "train not moving",
    "door": "door problem",
}

_ISSUE_LABELS_MS = {
    "delay": "kelewatan",
    "disruption": "gangguan",
    "incident": "masalah perkhidmatan",
    "technical_fault": "masalah teknikal",
    "crowding": "kesesakan",
    "outage": "gangguan",
    "stuck": "tren tak bergerak",
    "door": "masalah pintu",
}

_HEADLINE_MS = {
    "disruption": "Gangguan · {entity}",
    "delay": "Kelewatan · {entity}",
    "crowding": "Kesesakan · {entity}",
    "incident": "Isu · {entity}",
    "stuck": "Tren tak bergerak · {entity}",
    "door": "Masalah pintu · {entity}",
}

_FACILITY_KEYWORDS = (
    "lift",
    "lifts",
    "eskalator",
    "escalator",
    "wheelchair",
    "oku",
    "broken lift",
    "rosak",
    "lift rosak",
    "eskalator rosak",
)

_THREADS_CHROME_RE = re.compile(
    r"^(?:[a-z0-9_\.]{2,32}\s+\d{1,2}[hm]\s+)+",
    re.I,
)
_RELATIVE_TIME_RE = re.compile(r"\b(\d{1,3})\s*(min|mins|minute|minutes|minit|jam|hour|hours)\b", re.I)
_WAIT_RE = re.compile(r"\b(?:waiting|tunggu|kena tunggu)\b", re.I)


def _issue_key(cluster: dict) -> str:
    text = (cluster.get("example_text") or "").lower()
    cluster_id = str(cluster.get("cluster_id") or "")
    key = cluster_id.rsplit(":", 1)[-1].lower() if ":" in cluster_id else ""
    if key in _ISSUE_LABELS:
        return key
    if any(token in text for token in ["tak gerak", "not moving", "stuck", "tak bergerak"]):
        return "stuck"
    if any(token in text for token in ["pintu tak", "tak bukak", "door malfunction", "cannot board"]):
        return "door"
    severity = str(cluster.get("severity") or "low").lower()
    if any(token in text for token in ["suspend", "no service", "gangguan", "disruption", "evacuat", "fire alarm"]):
        return "disruption"
    if severity == "high":
        return "disruption"
    if any(token in text for token in ["delay", "lambat", "kelewatan", "waiting", "tunggu"]):
        return "delay"
    if any(token in text for token in ["sesak", "penuh", "crowd", "packed", "beratur"]):
        return "crowding"
    return "delay" if severity == "medium" else "incident"


def detect_facility_alert(cluster: dict) -> str | None:
    blob = " ".join(
        str(cluster.get(key) or "")
        for key in ("entity", "location", "example_text", "summary")
    ).lower()
    if not any(token in blob for token in _FACILITY_KEYWORDS):
        return None
    if any(token in blob for token in ("lift", "lifts", "eskalator", "escalator", "wheelchair", "oku")):
        return "facility"
    return None


def _fmt_myt_clock(parsed: datetime) -> str:
    local = parsed.astimezone(MYT)
    hour = local.hour % 12 or 12
    ampm = "AM" if local.hour < 12 else "PM"
    return f"{hour}:{local.minute:02d} {ampm} MYT"


def _relative_age_label(iso: str | None, *, now: datetime | None = None) -> str:
    parsed = parse_dt(iso)
    if parsed is None:
        return "time unknown"
    current = now or datetime.now(UTC)
    mins = max(0, int((current - parsed).total_seconds() // 60))
    if mins < 60:
        return f"{mins}m ago"
    hrs = mins // 60
    if parsed.astimezone(MYT).date() == current.astimezone(MYT).date():
        return f"{hrs}h ago"
    return _fmt_myt_clock(parsed)


def _relative_age_label_ms(iso: str | None, *, now: datetime | None = None) -> str:
    parsed = parse_dt(iso)
    if parsed is None:
        return "masa tidak diketahui"
    current = now or datetime.now(UTC)
    mins = max(0, int((current - parsed).total_seconds() // 60))
    if mins < 60:
        return f"{mins} min lalu"
    hrs = mins // 60
    if parsed.astimezone(MYT).date() == current.astimezone(MYT).date():
        return f"{hrs} jam lalu"
    return parsed.astimezone(MYT).strftime("%H:%M MYT")


def _clean_rider_quote(text: str, *, limit: int = 160) -> str:
    cleaned = _THREADS_CHROME_RE.sub("", (text or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ·|-")
    if len(cleaned) > limit:
        cleaned = cleaned[: limit - 1].rstrip() + "…"
    return cleaned


def _measured_wait_label(text: str) -> str:
    match = _RELATIVE_TIME_RE.search(text or "")
    if not match:
        return ""
    qty, unit = match.group(1), match.group(2).lower()
    if unit.startswith("jam") or unit.startswith("hour"):
        return f"~{qty} hr wait"
    return f"~{qty} min wait"


def _measured_wait_label_ms(text: str) -> str:
    match = _RELATIVE_TIME_RE.search(text or "")
    if not match:
        return ""
    qty, unit = match.group(1), match.group(2).lower()
    if unit.startswith("jam") or unit.startswith("hour"):
        return f"~{qty} jam tunggu"
    return f"~{qty} min tunggu"


def _issue_detail(text: str, issue_key: str) -> str:
    low = (text or "").lower()
    wait = _measured_wait_label(text)
    if wait:
        return wait
    if issue_key == "stuck":
        return "train not moving"
    if issue_key == "door":
        return "door not opening"
    if issue_key == "crowding":
        return "crowded platform/train"
    if issue_key == "disruption":
        return "service disruption"
    if _WAIT_RE.search(low):
        return "long wait"
    if "lambat" in low or "delay" in low:
        return "delayed"
    return _ISSUE_LABELS.get(issue_key, "service issue")


def _issue_detail_ms(text: str, issue_key: str) -> str:
    low = (text or "").lower()
    wait = _measured_wait_label_ms(text)
    if wait:
        return wait
    if issue_key == "stuck":
        return "tren tak bergerak"
    if issue_key == "door":
        return "pintu tak buka"
    if issue_key == "crowding":
        return "sesak / penuh"
    if issue_key == "disruption":
        return "gangguan perkhidmatan"
    if _WAIT_RE.search(low):
        return "tunggu lama"
    if "lambat" in low or "delay" in low:
        return "lewat"
    return _ISSUE_LABELS_MS.get(issue_key, "masalah perkhidmatan")


def public_incident_copy(cluster: dict) -> dict[str, str]:
    entity = str(cluster.get("entity") or "Transport").strip()
    location = str(cluster.get("location") or "").strip()
    text = str(cluster.get("example_text") or "")
    issue_key = _issue_key(cluster)
    when = _relative_age_label(cluster.get("last_seen_at") or cluster.get("first_seen_at"))
    when_ms = _relative_age_label_ms(cluster.get("last_seen_at") or cluster.get("first_seen_at"))
    issue = _issue_detail(text, issue_key)
    issue_ms = _issue_detail_ms(text, issue_key)
    quote = _clean_rider_quote(text)
    place = location if location and location.lower() not in entity.lower() else ""

    parts = [when, entity]
    if place:
        parts.append(place)
    parts.append(issue)
    glance = " · ".join(parts)
    parts_ms = [when_ms, entity]
    if place:
        parts_ms.append(place)
    parts_ms.append(issue_ms)
    glance_ms = " · ".join(parts_ms)

    headline_key = issue_key if issue_key in _HEADLINE_MS else "incident"
    headline = f"{entity} · {issue}" if not place else f"{entity} · {place} · {issue}"
    headline_ms = _HEADLINE_MS.get(headline_key, "Isu · {entity}").format(entity=entity)
    if place:
        headline_ms = f"{entity} · {place} · {issue_ms}"

    corroborated = bool(cluster.get("corroborated_by_official"))
    if corroborated:
        summary = quote or f"Rider report matched by an official notice — {issue}."
        summary_ms = quote or f"Laporan penumpang sepadan notis rasmi — {issue_ms}."
    else:
        summary = quote or f"Rider on {entity}{f' at {place}' if place else ''} — {issue}."
        summary_ms = quote or f"Penumpang di {entity}{f' di {place}' if place else ''} — {issue_ms}."

    facility_alert = detect_facility_alert(cluster)
    return {
        "headline": headline,
        "headline_ms": headline_ms,
        "glance_line": glance,
        "glance_line_ms": glance_ms,
        "summary": summary,
        "summary_ms": summary_ms,
        "facility_alert": facility_alert or "",
        "report_when": when,
        "report_when_ms": when_ms,
        "report_issue": issue,
        "report_issue_ms": issue_ms,
    }


def public_cluster(cluster: dict[str, Any]) -> dict[str, Any]:
    item = dict(cluster)
    item.update(public_incident_copy(cluster))
    item.pop("example_text", None)
    item.pop("author_handles", None)
    return item


def public_evidence(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_platform": item.get("source_platform", ""),
        "created_at": item.get("created_at", ""),
        "url": item.get("url", ""),
        "category": item.get("category", ""),
        "entity": item.get("entity", ""),
        "location": item.get("location", ""),
        "state": item.get("state", ""),
        "severity": item.get("severity", ""),
        "confidence": item.get("confidence", 0),
    }
