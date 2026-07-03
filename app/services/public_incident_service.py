from __future__ import annotations

from typing import Any


_ISSUE_LABELS = {
    "delay": "possible delays",
    "disruption": "a service disruption",
    "incident": "a service issue",
    "technical_fault": "a possible technical issue",
    "crowding": "crowding",
    "outage": "a service outage",
}

_ISSUE_LABELS_MS = {
    "delay": "kemungkinan kelewatan",
    "disruption": "gangguan perkhidmatan",
    "incident": "masalah perkhidmatan",
    "technical_fault": "kemungkinan masalah teknikal",
    "crowding": "kesesakan",
    "outage": "gangguan perkhidmatan",
}

_HEADLINE_MS = {
    "disruption": "Gangguan dilaporkan di {entity}",
    "delay": "Kelewatan mungkin di {entity}",
    "crowding": "Kesesakan dilaporkan di {entity}",
    "incident": "Isu perkhidmatan dilaporkan di {entity}",
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


def _issue_key(cluster: dict) -> str:
    cluster_id = str(cluster.get("cluster_id") or "")
    key = cluster_id.rsplit(":", 1)[-1].lower() if ":" in cluster_id else ""
    if key in _ISSUE_LABELS:
        return key
    severity = str(cluster.get("severity") or "low").lower()
    return "disruption" if severity == "high" else "delay" if severity == "medium" else "incident"


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


def public_incident_copy(cluster: dict) -> dict[str, str]:
    entity = str(cluster.get("entity") or "Transport service").strip()
    location = str(cluster.get("location") or "").strip()
    issue_key = _issue_key(cluster)
    issue = _ISSUE_LABELS[issue_key]
    issue_ms = _ISSUE_LABELS_MS.get(issue_key, issue)
    volume = int(cluster.get("volume", 0) or 0)
    source_count = int(cluster.get("source_count", 0) or 0)
    corroborated = bool(cluster.get("corroborated_by_official"))

    if issue_key == "disruption":
        headline = f"Disruption reported on {entity}"
    elif issue_key == "delay":
        headline = f"Possible delays on {entity}"
    elif issue_key == "crowding":
        headline = f"Crowding reported on {entity}"
    else:
        headline = f"Service issue reported on {entity}"

    headline_key = issue_key if issue_key in _HEADLINE_MS else "incident"
    headline_ms = _HEADLINE_MS[headline_key].format(entity=entity)

    place = f" near {location}" if location and location.lower() not in entity.lower() else ""
    place_ms = f" berhampiran {location}" if location and location.lower() not in entity.lower() else ""
    if corroborated:
        lead = "Recent rider signals and a time-matched official source indicate"
        caveat = "Supported by a recent operator or official-source notice."
        lead_ms = "Isyarat penumpang dan sumber rasmi yang sepadan menunjukkan"
        caveat_ms = "Disokong notis operator atau sumber rasmi terkini."
    elif volume >= 2 or source_count >= 2:
        lead = "Multiple recent rider signals indicate"
        caveat = "Awaiting operator confirmation."
        lead_ms = "Beberapa isyarat penumpang terkini menunjukkan"
        caveat_ms = "Menunggu pengesahan operator."
    else:
        lead = "A recent rider signal suggests"
        caveat = "Early signal; awaiting more reports or operator confirmation."
        lead_ms = "Isyarat penumpang terkini mencadangkan"
        caveat_ms = "Isyarat awal; menunggu lebih banyak laporan atau pengesahan operator."

    facility_alert = detect_facility_alert(cluster)
    return {
        "headline": headline,
        "headline_ms": headline_ms,
        "summary": f"{lead} {issue} affecting {entity}{place}. {caveat}",
        "summary_ms": f"{lead_ms} {issue_ms} melibatkan {entity}{place_ms}. {caveat_ms}",
        "facility_alert": facility_alert or "",
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
