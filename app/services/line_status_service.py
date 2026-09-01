from __future__ import annotations

from datetime import UTC, date, datetime, timedelta, timezone

from app.core.freshness import LIVE_WINDOW_DAYS, is_inside_myt_today, myt_today_date, parse_dt
from app.core.malaysia_transport_scope import is_malaysia_transport_cluster
from app.core.transport_lines import LINE_CATALOG, PLANNED_SERVICES, match_transport_line
from app.services.overview_service import (
    _is_real_transport_complaint,
    _matches_freshness_band,
    _matches_source_group,
    _sort_transport_clusters,
)
from app.services.incident_service import list_clusters
from app.services.malaysia_journey_hints import operator_commuter_note
from app.services.public_incident_service import detect_facility_alert, public_incident_copy
from app.services.headway_service import deviation as headway_deviation, extract_wait_minutes, scheduled_headway

def _severity_level(cluster: dict) -> str:
    text = (cluster.get("example_text") or "").lower()
    sev = cluster.get("severity", "low")
    if any(t in text for t in ["suspend", "no service", "terhenti total", "tutup"]):
        return "disruption"
    if any(t in text for t in ["fire alarm", "derail", "emergency", "evacuat", "kebakaran"]):
        return "disruption"
    if sev == "high" or any(t in text for t in ["gangguan", "disruption", "major"]):
        return "disruption"
    if sev == "medium" or any(t in text for t in ["delay", "lambat", "kelewatan", "problem", "rosak"]):
        return "delay"
    if cluster.get("freshness_bucket") == "recent":
        return "minor"
    return "minor"


_SEVERITY_RANK = {"unknown": 0, "minor": 1, "delay": 2, "disruption": 3}


def _health_score(*, status: str, report_count: int, corroborated: bool) -> int | None:
    if status == "unknown":
        return None
    score = 100 - _SEVERITY_RANK.get(status, 0) * 28 - min(report_count * 4, 24)
    if corroborated:
        score -= 8
    return max(0, min(100, score))


def _status_empty_label(status: str, report_count: int) -> str:
    if status != "unknown":
        return ""
    return "no_data"

_SEVERITY_LABEL = {
    "unknown": "No current signal",
    "minor": "Minor reports",
    "delay": "Delays reported",
    "disruption": "Disruption",
}

LINE_COLORS: dict[str, str] = {
    # Official operator colours, taken from `route_color` in the GTFS static
    # feeds published at api.data.gov.my (Prasarana rapid-rail-kl, KTMB).
    # Verified 2026-09-01. Every value here was previously an approximation —
    # BRT Sunway was rendered purple when the operator's colour is dark green.
    # These are wayfinding, not decoration: they must match station signage.
    "kelana-jaya": "#d50032",  # GTFS KJ  — LRT Kelana Jaya Line
    "ampang-sri-petaling": "#e57200",  # GTFS AG  — LRT Ampang Line (Sri Petaling is #76232f, see note)
    "kajang": "#047940",  # GTFS KGL — MRT Kajang Line
    "putrajaya": "#ffcd00",  # GTFS PYL — MRT Putrajaya Line
    "kajang-putrajaya": "#00a651",
    "monorail": "#84bd00",  # GTFS MR  — KL Monorail Line
    "brt-sunway": "#115740",  # GTFS BRT — BRT Sunway Line (was purple, actually dark green)
    "ktm-komuter": "#dc2420",  # GTFS KA15_KD19 — Tanjung Malim/Port Klang
    "ktm-north": "#018000",  # GTFS 100_47300 — Butterworth/Padang Besar
    "ets-intercity": "#ffc72c",  # GTFS ETS — Electric Train Service
    "klia-rail": "#7f1734",
    "sabah-railway": "#9b6a31",
    "rapid-bus": "#e21836",
    "penang": "#00843d",
    "kuantan": "#008b8b",
    "mybas": "#0f766e",
    "lrt3": "#00a9e0",  # GTFS SA  — LRT Shah Alam Line
    "ecrl": "#003d7a",
    "rts-johor": "#c41230",
    "mrt3": "#2563eb",
    "penang-lrt": "#0f766e",
}

LEGEND_GLOSSARY: list[dict[str, str]] = [
    {
        "term": "No current signal",
        "meaning": "No qualifying public report in the status window. This is not confirmation of normal service.",
    },
    {
        "term": "Minor reports",
        "meaning": "Recent complaints (slow, crowded, minor faults) that have not escalated to delay/disruption.",
    },
    {
        "term": "Delays reported",
        "meaning": "Multiple posts mention lateness, stuck trains, or kelewatan on this line.",
    },
    {
        "term": "Disruption",
        "meaning": "Suspension, evacuation, fire alarm, or no-service language in recent posts.",
    },
    {
        "term": "Ended for today",
        "meaning": "Last train has passed for this line (MYT). Earlier reports are cleared until service resumes.",
    },
    {
        "term": "Starts later today",
        "meaning": "Before first train on today's schedule. No live rider board until service opens.",
    },
    {
        "term": "Line colours",
        "meaning": "Stripe colours match official Rapid KL / KTMB route colours — functional only, not decoration.",
    },
]

# Status and feed use the MYT calendar day — resets at midnight Malaysia time.
STATUS_WINDOW_MODE = "myt_calendar_day"
STATUS_WINDOW_HOURS = 24  # legacy field; window is MYT calendar day, not rolling hours


def _inside_status_window(cluster: dict, *, now: datetime | None = None) -> bool:
    return is_inside_myt_today(
        cluster.get("last_seen_at") or cluster.get("first_seen_at"),
        now=now,
    )


def _inside_live_window(cluster: dict, *, now: datetime | None = None) -> bool:
    seen_at = parse_dt(cluster.get("last_seen_at") or cluster.get("first_seen_at"))
    if seen_at is None:
        return False
    current = now or datetime.now(UTC)
    return seen_at >= current - timedelta(days=LIVE_WINDOW_DAYS)


def get_legend_metadata(*, operational_only: bool = True) -> dict:
    today_myt = datetime.now(timezone(timedelta(hours=8))).date()
    specs = LINE_CATALOG
    if operational_only:
        specs = [
            spec
            for spec in LINE_CATALOG
            if not spec.get("service_start_date")
            or datetime.fromisoformat(spec["service_start_date"]).date() <= today_myt
        ]
    lines = [
        {
            "id": spec["id"],
            "name": spec["name"],
            "mode": spec.get("mode", "rail"),
            "color": LINE_COLORS.get(spec["id"], "#64748b"),
            "operator": spec.get("operator", ""),
        }
        for spec in specs
    ]
    return {
        "title": "Line colours = official route colours",
        "lines": lines,
        "glossary": LEGEND_GLOSSARY,
        "status_window_mode": STATUS_WINDOW_MODE,
        "status_date_myt": myt_today_date().isoformat(),
        "live_window_days": LIVE_WINDOW_DAYS,
    }


def _service_status_for_line(line_id: str, *, now: datetime | None = None) -> dict:
    from app.services.line_reference_service import _reference_by_id, compute_service_status_now

    ref = _reference_by_id().get(line_id, {})
    return compute_service_status_now(ref.get("operating_hours"), now=now)


def _ended_for_today_label(service_phase: str) -> str:
    if service_phase == "after_service":
        return "Ended for today"
    if service_phase == "before_service":
        return "Starts later today"
    if service_phase == "not_operating":
        return "Not in service"
    return "No current signal"


def get_line_status_board(
    *,
    source_group: str = "social",
    quality_only: bool = True,
    malaysia_only: bool = True,
    as_of: date | None = None,
    now: datetime | None = None,
) -> dict:
    current = now or datetime.now(UTC)
    today_myt = as_of or current.astimezone(timezone(timedelta(hours=8))).date()
    operational_specs = [
        spec
        for spec in LINE_CATALOG
        if not spec.get("service_start_date")
        or datetime.fromisoformat(spec["service_start_date"]).date() <= today_myt
    ]
    scheduled_specs = [spec for spec in LINE_CATALOG if spec not in operational_specs]
    clusters = list_clusters(category="transport")
    clusters = [c for c in clusters if _matches_source_group(c, source_group)]
    if malaysia_only:
        clusters = [c for c in clusters if is_malaysia_transport_cluster(c)]
    if quality_only:
        clusters = [c for c in clusters if _is_real_transport_complaint(c)]
    clusters = [c for c in clusters if _matches_freshness_band(c, "all")]
    status_clusters = [c for c in clusters if _inside_status_window(c, now=current)]
    report_clusters = [c for c in clusters if _inside_status_window(c, now=current)]
    status_clusters = _sort_transport_clusters(status_clusters, sort_by="freshest")
    report_clusters = [c for c in report_clusters if _is_real_transport_complaint(c)]
    report_clusters = _sort_transport_clusters(report_clusters, sort_by="freshest")

    by_line: dict[str, list[dict]] = {line["id"]: [] for line in operational_specs}
    unmatched: list[dict] = []

    for cluster in status_clusters:
        if cluster.get("subcategory") == "line_info":
            continue
        line_id = match_transport_line(cluster)
        if line_id in by_line:
            by_line[line_id].append(cluster)
        else:
            unmatched.append(cluster)

    lines_out: list[dict] = []
    for spec in operational_specs:
        items = by_line[spec["id"]]
        if not items:
            level = "unknown"
            reason = ""
            report_count = 0
            last_seen = None
            top_cluster = None
            reported_wait = None
        else:
            levels = [_severity_level(c) for c in items]
            level = max(levels, key=lambda x: _SEVERITY_RANK[x])
            top = items[0]
            top_cluster = top.get("cluster_id")
            # Largest measured platform wait across today's reports for this
            # line. None unless a rider actually wrote a number down.
            reported_wait = max(
                (extract_wait_minutes(c.get("example_text") or "") or 0 for c in items),
                default=0,
            ) or None
            reason = public_incident_copy(top)["summary"]
            report_count = sum(c.get("volume", 1) for c in items)
            last_seen = top.get("last_seen_at")
        facility_alert = None
        if items:
            for cluster in items:
                facility_alert = detect_facility_alert(cluster)
                if facility_alert:
                    break
        commuter_note = operator_commuter_note(spec["id"])
        service_now = _service_status_for_line(spec["id"], now=current)
        in_service = service_now.get("in_service")
        service_phase = service_now.get("status", "unknown")
        service_label = service_now.get("label", "")
        status_label = _SEVERITY_LABEL[level]
        empty_state = _status_empty_label(level, report_count)

        if in_service is False:
            level = "unknown"
            status_label = _ended_for_today_label(service_phase)
            empty_state = "service_ended" if service_phase == "after_service" else "before_service"
            reason = ""
            top_cluster = None
            report_count = 0
            facility_alert = None
            reported_wait = None

        # Scheduled headway and deviation only when the line is running and
        # actually has reports. Keeps the quiet-board path free of GTFS work.
        headway = scheduled_headway(spec["id"], last_seen) if items and in_service is not False else None
        deviation = (
            headway_deviation(spec["id"], reported_wait, last_seen)
            if reported_wait and in_service is not False
            else None
        )

        lines_out.append(
            {
                "id": spec["id"],
                "name": spec["name"],
                "mode": spec["mode"],
                "operator": spec["operator"],
                "region": spec["region"],
                "route": spec["route"],
                "service_hours": spec["service_hours"],
                "peak_frequency": spec["peak_frequency"],
                "timetable_url": spec["timetable_url"],
                "status": level,
                "status_label": status_label,
                "empty_state": empty_state,
                "health_score": _health_score(status=level, report_count=report_count, corroborated=any(c.get("corroborated_by_official") for c in items) if items and in_service is not False else False),
                "reason": reason,
                "report_count": report_count,
                "last_seen_at": last_seen if in_service is not False else None,
                "top_cluster_id": top_cluster,
                "sources": items[0].get("sources", "") if items and in_service is not False else "",
                "corroborated": any(c.get("corroborated_by_official") for c in items) if items and in_service is not False else False,
                "commuter_note": commuter_note,
                "commuter_note_ms": operator_commuter_note(spec["id"], lang="ms"),
                "facility_alert": facility_alert,
                "in_service": in_service,
                "service_status": service_phase,
                "reported_wait_min": reported_wait,
                "headway": headway,
                "deviation": deviation,
                "service_label": service_label,
            }
        )

    active_lines = sum(
        1
        for line in lines_out
        if line.get("in_service") is not False and line["status"] in {"minor", "delay", "disruption"}
    )
    modes_breakdown: dict[str, int] = {}
    for spec in operational_specs:
        mode = spec.get("mode", "other")
        modes_breakdown[mode] = modes_breakdown.get(mode, 0) + 1
    status_date = today_myt.isoformat()
    if active_lines == 0:
        board_summary = f"No active disruption signal today ({status_date} MYT) — quiet is not an all-clear"
    else:
        board_summary = (
            f"{active_lines} line{'s' if active_lines != 1 else ''} "
            f"with rider reports today ({status_date} MYT)"
        )
    return {
        "product": "TrafficMY",
        "scope": "malaysia",
        "live_window_days": LIVE_WINDOW_DAYS,
        "status_window_mode": STATUS_WINDOW_MODE,
        "status_date_myt": status_date,
        "status_window_hours": 24,
        "lines_tracked_count": len(operational_specs),
        "modes_breakdown": modes_breakdown,
        "board_summary": board_summary,
        "active_line_count": active_lines,
        "active_alert_count": active_lines,
        "lines": lines_out,
        "legend": get_legend_metadata(),
        "recent_reports": report_clusters[:12],
        "unmatched_reports": unmatched[:5],
        "planned_services": [
            {
                "id": spec["id"],
                "name": spec["name"],
                "route": spec["route"],
                "stage": f"Passenger service starts {spec['service_start_date']}",
                "operator": spec["operator"],
                "url": spec["timetable_url"],
            }
            for spec in scheduled_specs
        ]
        + PLANNED_SERVICES,
    }


def clean_reason(text: str) -> str:
    import re

    t = text.strip()
    t = re.sub(r"^[\w.@]+[\s\u00b7]+(\d+[hdwms]?|\d{1,2}/\d{1,2}/\d{2,4})\s*", "", t, flags=re.I)
    t = re.sub(r"^Replying to @\w+\s*", "", t, flags=re.I)
    t = re.sub(r"\s+", " ", t)
    return t[:140]
