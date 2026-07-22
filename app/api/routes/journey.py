from fastapi import APIRouter, HTTPException, Query

from app.services.fare_service import estimate_journey_fare
from app.services.journey_service import list_rail_stations, plan_rail_journey
from app.services.malaysia_journey_hints import enrich_journey_plan
from app.services.map_service import get_live_map, get_map_stations, get_rail_lines_geojson, get_station_detail
from app.services.places_service import list_stations
from app.services.transport_update_service import compare_rapid_passes, get_transport_updates

router = APIRouter()


@router.get("/trafficmy/stations")
def trafficmy_stations(
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict:
    items = list_stations(q=q, limit=limit)
    source = "gtfs" if items and items[0].get("source") == "gtfs" else "locations.yaml"
    return {"items": items, "source": source}


@router.get("/trafficmy/journey/stations")
def journey_stations(
    q: str = Query(default="", max_length=80),
    limit: int = Query(default=12, ge=1, le=30),
) -> dict:
    return {"items": list_rail_stations(q, limit=limit), "source": "Malaysia government GTFS"}


@router.get("/trafficmy/journey/plan")
def journey_plan(
    origin: str = Query(min_length=2, max_length=120),
    destination: str = Query(min_length=2, max_length=120),
) -> dict:
    try:
        result = plan_rail_journey(origin, destination)
        ride_legs = sum(1 for leg in result.get("legs") or [] if leg.get("kind") == "ride")
        result["fare"] = estimate_journey_fare(ride_legs=ride_legs, transfers=result.get("transfers", 0))
        return enrich_journey_plan(result)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/trafficmy/map/live")
def map_live(
    vehicles: bool = Query(default=False, description="Include GTFS-RT bus GPS (optional, may lag)"),
    vehicle_limit: int = Query(default=60, ge=1, le=120),
    report_limit: int = Query(default=80, ge=10, le=150),
) -> dict:
    return get_live_map(
        include_vehicles=vehicles,
        vehicle_limit=vehicle_limit,
        report_limit=report_limit,
    )


@router.get("/trafficmy/map/stations")
def map_stations(
    limit: int = Query(default=120, ge=10, le=200),
    layer: str = Query(default="rail", pattern="^(rail|bus)$"),
) -> dict:
    return get_map_stations(limit=limit, layer=layer)


@router.get("/trafficmy/map/rail-lines")
def map_rail_lines() -> dict:
    return get_rail_lines_geojson()


@router.get("/trafficmy/map/station")
def map_station_detail(name: str = Query(min_length=2, max_length=120)) -> dict:
    detail = get_station_detail(name)
    if detail is None:
        raise HTTPException(status_code=404, detail="Station not found in Malaysia GTFS")
    return detail


@router.get("/trafficmy/updates")
def transport_updates() -> dict:
    return get_transport_updates()


@router.get("/trafficmy/pass-comparison")
def pass_comparison(
    rides_per_month: int = Query(default=40, ge=1, le=200),
    average_fare: float = Query(default=3.0, ge=0.5, le=20),
    malaysian: bool = Query(default=True),
    student: bool = Query(default=False),
) -> dict:
    return compare_rapid_passes(
        rides_per_month=rides_per_month,
        average_fare=average_fare,
        malaysian=malaysian,
        student=student,
    )
