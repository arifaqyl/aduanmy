from fastapi import APIRouter, HTTPException, Query

from app.services.incident_service import get_cluster_detail, list_clusters, list_complaints
from app.services.ingest_service import run_ingest
from app.services.overview_service import get_trafficmy_incidents, get_trafficmy_overview
from app.services.status_service import get_trafficmy_status

router = APIRouter()


@router.get("/complaints")
def complaints(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    return {"items": list_complaints(limit)}


@router.get("/clusters")
def clusters(
    category: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    confidence_band: str | None = Query(default=None),
) -> dict:
    return {
        "items": list_clusters(
            category=category,
            severity=severity,
            confidence_band=confidence_band,
        )
    }


@router.get("/clusters/{cluster_id:path}")
def cluster_detail(cluster_id: str) -> dict:
    detail = get_cluster_detail(cluster_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Cluster not found")
    return detail


@router.post("/refresh")
def refresh() -> dict:
    report = run_ingest()
    return {
        "status": "ok",
        "ingest": report,
        "cluster_count": len(list_clusters()),
    }


@router.get("/trafficmy/overview")
def trafficmy_overview(
    include_stale: bool = Query(default=False),
) -> dict:
    return get_trafficmy_overview(include_stale=include_stale)


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
    include_stale: bool = Query(default=False),
) -> dict:
    return get_trafficmy_incidents(
        sort_by=sort_by,
        confidence_band=confidence_band,
        severity=severity,
        entity=entity,
        location=location,
        include_stale=include_stale,
    )


@router.get("/trafficmy/incidents/{cluster_id:path}")
def trafficmy_incident_detail(cluster_id: str) -> dict:
    detail = get_cluster_detail(cluster_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {
        "product": "TrafficMY",
        "incident": detail["cluster"],
        "source_breakdown": detail["source_breakdown"],
        "items": detail["items"],
    }
