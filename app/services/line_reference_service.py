from __future__ import annotations

import json
import re
from datetime import UTC, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path

from app.core.freshness import is_inside_myt_today
from app.core.transport_lines import LINE_CATALOG, match_transport_line
from app.services.incident_service import list_clusters
from app.services.line_status_service import LINE_COLORS, get_line_status_board
from app.services.overview_service import _is_real_transport_complaint
from app.services.public_incident_service import public_incident_copy

_REFERENCE_PATH = Path(__file__).resolve().parents[2] / "static" / "data" / "lines-reference.json"
_MYT = timezone(timedelta(hours=8))

@lru_cache(maxsize=1)
def _load_reference() -> dict:
    if not _REFERENCE_PATH.exists():
        return {"version": 1, "scope": "malaysia", "lines": []}
    return json.loads(_REFERENCE_PATH.read_text(encoding="utf-8"))


def _reference_by_id() -> dict[str, dict]:
    return {line["id"]: line for line in _load_reference().get("lines", [])}


def _parse_hm(value: str) -> time | None:
    if not value:
        return None
    match = re.match(r"^(\d{1,2}):(\d{2})$", value.strip())
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def _minutes_since_midnight(value: time) -> int:
    return value.hour * 60 + value.minute


def compute_service_status_now(
    operating_hours: dict | None,
    *,
    now: datetime | None = None,
) -> dict:
    """Client/server shared semantics for live service window (MYT, static schedule)."""
    if not operating_hours:
        return {"status": "unknown", "label": "Hours not available", "in_service": None}

    current = (now or datetime.now(UTC)).astimezone(_MYT)
    if operating_hours.get("service_start_date"):
        try:
            start_date = datetime.fromisoformat(operating_hours["service_start_date"]).date()
            if current.date() < start_date:
                return {
                    "status": "not_operating",
                    "label": f"Passenger service from {start_date.strftime('%d %b %Y')}",
                    "in_service": False,
                }
        except ValueError:
            pass

    first = _parse_hm(operating_hours.get("first_train", ""))
    last = _parse_hm(operating_hours.get("last_train", ""))
    if first is None or last is None:
        return {"status": "unknown", "label": "Hours not available", "in_service": None}

    now_min = current.hour * 60 + current.minute
    first_min = _minutes_since_midnight(first)
    last_min = _minutes_since_midnight(last)
    if last_min <= first_min:
        last_min += 24 * 60
        if now_min < first_min:
            now_min += 24 * 60

    if now_min < first_min:
        return {
            "status": "before_service",
            "label": f"Starts {operating_hours.get('first_train', '')} MYT",
            "in_service": False,
        }
    if now_min > last_min:
        return {
            "status": "after_service",
            "label": "Service ended",
            "in_service": False,
        }

    for peak in operating_hours.get("peak_hours") or []:
        peak_start = _parse_hm(peak.get("start", ""))
        peak_end = _parse_hm(peak.get("end", ""))
        if peak_start is None or peak_end is None:
            continue
        ps, pe = _minutes_since_midnight(peak_start), _minutes_since_midnight(peak_end)
        if ps <= now_min <= pe:
            headway = peak.get("headway_min")
            freq = f"Every ~{headway} min" if headway else "Peak frequency"
            return {
                "status": "peak",
                "label": f"Rush hour now · {freq}",
                "in_service": True,
                "peak_label": peak.get("label", "Peak"),
            }

    off_peak = operating_hours.get("off_peak_headway_min")
    freq = f"Every ~{off_peak} min" if off_peak else "Off-peak"
    return {"status": "off_peak", "label": f"Off-peak · {freq}", "in_service": True}


def _enrich_interchange(item: dict) -> dict:
    out = dict(item)
    line_ids = list(item.get("connects_to_line_ids") or [])
    if not line_ids and item.get("connects_to"):
        blob = item["connects_to"].lower()
        for spec in LINE_CATALOG:
            if spec["name"].lower() in blob or spec["id"].replace("-", " ") in blob:
                line_ids.append(spec["id"])
    out["connects_to_line_ids"] = line_ids
    out["line_colours"] = [
        {"id": lid, "color": LINE_COLORS.get(lid, "#64748b")} for lid in line_ids
    ]
    return out


def get_all_interchanges() -> dict:
    """Hub stations indexed for map layer and browse."""
    hubs: dict[str, dict] = {}
    for line_id, ref in _reference_by_id().items():
        for raw in ref.get("interchanges") or []:
            station = raw.get("station", "").strip()
            if not station:
                continue
            key = station.lower()
            enriched = _enrich_interchange(raw)
            if key not in hubs:
                hubs[key] = {
                    "station": station,
                    "lines": [],
                    "connections": [],
                }
            if line_id not in hubs[key]["lines"]:
                hubs[key]["lines"].append(line_id)
            hubs[key]["connections"].append(
                {
                    "from_line_id": line_id,
                    "from_line_name": ref.get("name", line_id),
                    "connects_to": enriched.get("connects_to", ""),
                    "connects_to_line_ids": enriched.get("connects_to_line_ids", []),
                    "walking_note": enriched.get("walking_note", ""),
                    "line_colours": enriched.get("line_colours", []),
                }
            )
    items = sorted(hubs.values(), key=lambda row: row["station"])
    return {"product": "TrafficMY", "scope": "malaysia", "hubs": items, "count": len(items)}


def list_lines_reference() -> dict:
    """Summary list for legend and browse UI."""
    ref_map = _reference_by_id()
    items: list[dict] = []
    for spec in LINE_CATALOG:
        ref = ref_map.get(spec["id"], {})
        hours = ref.get("operating_hours")
        items.append(
            {
                "id": spec["id"],
                "name": spec["name"],
                "operator": spec.get("operator", ref.get("operator", "")),
                "mode": spec.get("mode", ref.get("mode", "rail")),
                "endpoints": ref.get("endpoints"),
                "where_it_goes": ref.get("where_it_goes") or spec.get("route", ""),
                "official_colour": ref.get("official_colour") or LINE_COLORS.get(spec["id"], "#64748b"),
                "has_schematic": bool(ref.get("schematic_svg")),
                "schematic_svg": ref.get("schematic_svg"),
                "interchange_count": len(ref.get("interchanges") or []),
                "operating_hours": hours,
                "service_status_now": compute_service_status_now(hours),
            }
        )
    return {
        "product": "TrafficMY",
        "scope": "malaysia",
        "lines": items,
        "count": len(items),
    }


def get_line_reference(line_id: str) -> dict | None:
    ref = _reference_by_id().get(line_id)
    if not ref:
        spec = next((s for s in LINE_CATALOG if s["id"] == line_id), None)
        if not spec:
            return None
        ref = {
            "id": spec["id"],
            "name": spec["name"],
            "operator": spec.get("operator", ""),
            "mode": spec.get("mode", "rail"),
            "where_it_goes": spec.get("route", ""),
            "official_colour": LINE_COLORS.get(spec["id"], "#64748b"),
        }
    enriched = dict(ref)
    enriched["interchanges"] = [_enrich_interchange(item) for item in ref.get("interchanges") or []]
    return enriched


def _rider_reports(line_id: str, *, limit: int = 5) -> list[dict]:
    """Recent crowd reports for a line — Threads-first."""
    ref = get_line_reference(line_id) or {}
    keywords = [line_id.replace("-", " ")] + list(ref.get("keywords") or [])
    snippets: list[dict] = []
    for cluster in list_clusters(category="transport"):
        if cluster.get("subcategory") == "line_info":
            continue
        if not _is_real_transport_complaint(cluster):
            continue
        if not is_inside_myt_today(cluster.get("last_seen_at") or cluster.get("first_seen_at")):
            continue
        matched = match_transport_line(cluster) == line_id
        if not matched:
            blob = (cluster.get("example_text") or "").lower()
            matched = any(kw in blob for kw in keywords if len(kw) > 3)
        if not matched:
            continue
        sources = cluster.get("sources") or ""
        copy = public_incident_copy(cluster)
        snippets.append(
            {
                "cluster_id": cluster.get("cluster_id"),
                "headline": copy["headline"],
                "summary": copy["summary"],
                "glance_line": copy.get("glance_line", copy["headline"]),
                "last_seen_at": cluster.get("last_seen_at"),
                "sources": sources,
                "example_url": cluster.get("example_url"),
                "from_threads": "threads" in sources,
            }
        )
        if len(snippets) >= limit:
            break
    snippets.sort(key=lambda row: row.get("last_seen_at") or "", reverse=True)
    return snippets


def _social_info_snippets(line_id: str, *, limit: int = 3) -> list[dict]:
    ref = get_line_reference(line_id) or {}
    keywords = [line_id.replace("-", " ")] + list(ref.get("keywords") or [])
    snippets: list[dict] = []
    for cluster in list_clusters(category="transport"):
        if cluster.get("subcategory") != "line_info":
            continue
        matched = match_transport_line(cluster) == line_id
        if not matched:
            blob = (cluster.get("example_text") or "").lower()
            matched = any(kw in blob for kw in keywords if len(kw) > 3)
        if not matched:
            continue
        copy = public_incident_copy(cluster)
        snippets.append(
            {
                "cluster_id": cluster.get("cluster_id"),
                "headline": copy["headline"],
                "summary": copy["summary"],
                "last_seen_at": cluster.get("last_seen_at"),
                "sources": cluster.get("sources", ""),
            }
        )
        if len(snippets) >= limit:
            break
    return snippets


def get_line_info(line_id: str) -> dict | None:
    ref = get_line_reference(line_id)
    if ref is None:
        return None
    board = get_line_status_board()
    status = next((line for line in board["lines"] if line["id"] == line_id), None)
    spec = next((s for s in LINE_CATALOG if s["id"] == line_id), None)
    schematic = ref.get("schematic_svg")
    hours = ref.get("operating_hours")
    return {
        "product": "TrafficMY",
        "scope": "malaysia",
        "reference": ref,
        "status": status,
        "operating_hours": hours,
        "service_status_now": compute_service_status_now(hours),
        "stations_ordered": ref.get("stations_ordered") or ref.get("major_stations") or [],
        "timetable_url": spec.get("timetable_url") if spec else None,
        "schematic_url": f"/static/{schematic}" if schematic else None,
        "line_facts": ref.get("line_facts") or [],
        "rider_reports": _rider_reports(line_id),
        "social_info": _social_info_snippets(line_id),
    }


def service_status_for_line(line_id: str, *, now: datetime | None = None) -> dict:
    ref = _reference_by_id().get(line_id) or {}
    return compute_service_status_now(ref.get("operating_hours"), now=now)
