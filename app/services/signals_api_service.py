"""Machine-readable today signals — B2B / embed / integrations."""
from __future__ import annotations

from datetime import UTC, datetime

from app.core.freshness import myt_today_date
from app.core.transport_lines import match_transport_line
from app.services.line_status_service import STATUS_WINDOW_MODE, get_line_status_board
from app.services.public_incident_service import public_incident_copy, public_cluster
from app.services.overview_service import _is_real_transport_complaint


def get_today_signals(*, limit: int = 25) -> dict:
    board = get_line_status_board(source_group="social", quality_only=True, malaysia_only=True)
    lines = board.get("lines") or []
    reports = board.get("recent_reports") or []

    active = [line for line in lines if line.get("status") in {"minor", "delay", "disruption"}]
    signals: list[dict] = []
    for cluster in reports[:limit]:
        if not _is_real_transport_complaint(cluster):
            continue
        public = public_cluster(cluster)
        sources = [s.strip() for s in (cluster.get("sources") or "").split(",") if s.strip()]
        signals.append(
            {
                "id": public.get("cluster_id", ""),
                "glance_line": public.get("glance_line", public.get("headline", "")),
                "glance_line_ms": public.get("glance_line_ms", public.get("headline_ms", "")),
                "headline": public.get("headline", ""),
                "summary": public.get("summary", ""),
                "entity": public.get("entity", cluster.get("entity", "")),
                "location": public.get("location", cluster.get("location", "")),
                "line_id": match_transport_line(cluster) or "",
                "issue": public.get("report_issue", ""),
                "severity": public.get("severity", "low"),
                "status": public.get("severity", "low"),
                "when": public.get("report_when", ""),
                "last_seen_at": public.get("last_seen_at", cluster.get("last_seen_at", "")),
                "sources": sources,
                "corroborated_by_official": bool(cluster.get("corroborated_by_official")),
                "confidence_band": public.get("confidence_band", ""),
                "example_url": public.get("example_url", cluster.get("example_url", "")),
            }
        )

    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    status_date = board.get("status_date_myt") or myt_today_date().isoformat()
    return {
        "product": "TrafficMY",
        "schema_version": "1",
        "kind": "live_rider_signals_today",
        "as_of": now,
        "status_date_myt": status_date,
        "status_window_mode": board.get("status_window_mode", STATUS_WINDOW_MODE),
        "summary": {
            "headline": board.get("board_summary", ""),
            "active_lines": board.get("active_line_count", 0),
            "reports_today": len(signals),
            "lines_tracked": board.get("lines_tracked_count", len(lines)),
            "quiet_is_not_all_clear": True,
        },
        "differentiator": (
            "Live rider-reported delays and disruptions for today (MYT). "
            "Not historical ridership statistics or operator schedules."
        ),
        "lines": [
            {
                "id": line.get("id"),
                "name": line.get("name"),
                "status": line.get("status"),
                "status_label": line.get("status_label"),
                "report_count": line.get("report_count", 0),
                "in_service": line.get("in_service", True),
                "color": line.get("color"),
                "mode": line.get("mode"),
            }
            for line in lines
        ],
        "signals": signals,
        "attribution": "TrafficMY · rider signals today · not an official all-clear",
        "license_note": "Summaries only; link to source URLs where provided. Contact for commercial API keys.",
        "links": {
            "app": "/",
            "methodology": "/methodology",
            "developers": "/developers",
            "openapi": "/docs",
        },
    }
