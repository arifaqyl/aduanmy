from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException, Query, Request

from app.core.config import settings
from app.services.config_service import get_trafficmy_config
from app.services.line_reference_service import get_line_info, list_lines_reference
from app.services.line_status_service import get_line_status_board
from app.services.incident_service import get_cluster_detail, list_clusters, list_complaints
from app.services.overview_service import get_trafficmy_incidents, get_trafficmy_overview
from app.services.methodology_service import get_methodology
from app.services.status_service import get_trafficmy_status
from app.services.scheduler_service import trigger_full_ingest_async, run_full_now
from app.services.public_incident_service import public_cluster, public_evidence

router = APIRouter()


def _refresh_allowed(
    *,
    x_api_key: str | None,
    referer: str | None,
    dashboard_header: str | None,
    request_host: str | None = None,
) -> bool:
    if not settings.refresh_api_key:
        return True
    if x_api_key == settings.refresh_api_key:
        return True
    if settings.allow_dashboard_refresh and dashboard_header == "1":
        if settings.env != "production":
            return True
        return bool(referer and request_host and urlparse(referer).netloc == request_host)
    if settings.allow_dashboard_refresh and referer and "/traffic" in referer:
        return True
    return False


@router.get("/complaints")
def complaints(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    items = list_complaints(limit)
    if settings.expose_raw_sources:
        return {"items": items}
    return {"items": [public_evidence(item) for item in items]}


@router.get("/clusters")
def clusters(
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    confidence_band: str | None = Query(default=None),
) -> dict:
    items = list_clusters(
        category=category,
        severity=severity,
        confidence_band=confidence_band,
    )
    return {"items": items if settings.expose_raw_sources else [public_cluster(item) for item in items]}


@router.get("/clusters/{cluster_id:path}")
def cluster_detail(cluster_id: str) -> dict:
    detail = get_cluster_detail(cluster_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Cluster not found")
    if settings.expose_raw_sources:
        return detail
    return {
        "cluster": public_cluster(detail["cluster"]),
        "source_breakdown": detail["source_breakdown"],
        "items": [public_evidence(item) for item in detail["items"]],
    }


@router.post("/refresh")
def refresh(
    request: Request,
    sync: bool = False,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    referer = request.headers.get("referer", "")
    dashboard_header = request.headers.get("x-dashboard-refresh", "")
    if not _refresh_allowed(
        x_api_key=x_api_key,
        referer=referer,
        dashboard_header=dashboard_header,
        request_host=request.headers.get("host"),
    ):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

    if sync:
        report = run_full_now()
        if report is None:
            raise HTTPException(status_code=409, detail="An ingest is already running")
        return {
            "status": "ok",
            "ingest": report,
            "cluster_count": report.get("written", 0),
        }

    success = trigger_full_ingest_async()
    if not success:
        raise HTTPException(status_code=409, detail="An ingest is already running")
    return {
        "status": "accepted",
        "message": "Refresh started in background",
    }


@router.get("/trafficmy/interchanges")
def trafficmy_interchanges() -> dict:
    from app.services.line_reference_service import get_all_interchanges

    return get_all_interchanges()


@router.get("/trafficmy/lines/reference")
def trafficmy_lines_reference() -> dict:
    return list_lines_reference()


@router.get("/trafficmy/lines/{line_id}/info")
def trafficmy_line_info(line_id: str) -> dict:
    info = get_line_info(line_id)
    if info is None:
        raise HTTPException(status_code=404, detail="Line not found")
    return info


@router.get("/trafficmy/lines")
def trafficmy_lines(
    source_group: str = Query(default="social", pattern="^(social|gps|all)$"),
    quality_only: bool = Query(default=True),
    malaysia_only: bool = Query(default=True),
) -> dict:
    payload = get_line_status_board(
        source_group=source_group,
        quality_only=quality_only,
        malaysia_only=malaysia_only,
    )
    payload["recent_reports"] = [public_cluster(item) for item in payload.get("recent_reports", [])]
    payload["unmatched_reports"] = [public_cluster(item) for item in payload.get("unmatched_reports", [])]
    return payload


@router.get("/trafficmy/config")
def trafficmy_config() -> dict:
    return get_trafficmy_config()


@router.get("/trafficmy/brand")
def trafficmy_brand() -> dict:
    return {
        "name": "TrafficMY Pulse",
        "short_name": "TrafficMY",
        "tagline": "Malaysia transport intelligence",
        "mission": "Crowd-reported delays and disruptions. Quiet lines mean no recent qualifying signal — not confirmed normal service.",
        "version": "2026.07",
        "mobile_first": True,
    }


@router.get("/trafficmy/meta")
def trafficmy_meta() -> dict:
    config = get_trafficmy_config()
    return {
        "product": "TrafficMY Pulse",
        "tagline": "Malaysia transport intelligence",
        "status_window_hours": config.get("status_window_hours", 24),
        "refresh_interval_seconds": config.get("poll_interval_seconds"),
        "ingest_interval_seconds": config.get("ingest_interval_seconds"),
        "mobile_first": True,
    }


@router.get("/trafficmy/app-shell")
def trafficmy_app_shell() -> dict:
    config = get_trafficmy_config()
    status = get_trafficmy_status()
    return {
        "brand": trafficmy_brand(),
        "meta": {
            "product": "TrafficMY Pulse",
            "tagline": "Malaysia transport intelligence",
            "status_window_hours": config.get("status_window_hours", 24),
            "refresh_interval_seconds": config.get("poll_interval_seconds"),
            "ingest_interval_seconds": config.get("ingest_interval_seconds"),
            "mobile_first": True,
        },
        "config": config,
        "status": {
            "freshness": status.get("freshness", {}),
            "scheduler": status.get("scheduler", {}),
        },
    }


@router.get("/trafficmy/overview")
def trafficmy_overview(
    include_stale: bool = Query(default=False),
    source_group: str = Query(default="social", pattern="^(social|gps|all)$"),
    quality_only: bool = Query(default=True),
    malaysia_only: bool = Query(default=True),
) -> dict:
    payload = get_trafficmy_overview(
        include_stale=include_stale,
        source_group=source_group,
        quality_only=quality_only,
        malaysia_only=malaysia_only,
    )
    payload["top_incidents"] = [public_cluster(item) for item in payload.get("top_incidents", [])]
    return payload


@router.get("/trafficmy/methodology")
def trafficmy_methodology() -> dict:
    return get_methodology()


@router.get("/trafficmy/status")
def trafficmy_status() -> dict:
    return get_trafficmy_status()


@router.get("/trafficmy/incidents")
def trafficmy_incidents(
    sort_by: str = Query(default="strongest", pattern="^(strongest|freshest)$"),
    confidence_band: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    entity: str | None = Query(default=None),
    location: str | None = Query(default=None),
    state: str | None = Query(default=None),
    mode: str | None = Query(default=None, pattern="^(bus|rail)$"),
    source_group: str = Query(default="social", pattern="^(social|gps|all)$"),
    freshness_band: str = Query(default="recent", pattern="^(recent|aging|all)$"),
    quality_only: bool = Query(default=True),
    include_stale: bool = Query(default=False),
    malaysia_only: bool = Query(default=True),
) -> dict:
    payload = get_trafficmy_incidents(
        sort_by=sort_by,
        confidence_band=confidence_band,
        severity=severity,
        entity=entity,
        location=location,
        state=state,
        mode=mode,
        source_group=source_group,
        freshness_band=freshness_band,
        quality_only=quality_only,
        include_stale=include_stale,
        malaysia_only=malaysia_only,
    )
    payload["items"] = [public_cluster(item) for item in payload.get("items", [])]
    return payload


@router.get("/trafficmy/incidents/{cluster_id:path}")
def trafficmy_incident_detail(cluster_id: str) -> dict:
    detail = get_cluster_detail(cluster_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        "product": "TrafficMY",
        "incident": public_cluster(detail["cluster"]),
        "source_breakdown": detail["source_breakdown"],
        "items": [public_evidence(item) for item in detail["items"]],
    }
