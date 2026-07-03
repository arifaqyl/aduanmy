from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from app.core.transport_lines import LINE_CATALOG, match_transport_line
from app.core.freshness import is_inside_myt_today
from app.services.incident_service import list_clusters
from app.services.journey_service import _graph, _normalise
from app.services.line_status_service import LINE_COLORS, get_line_status_board
from app.services.public_incident_service import public_incident_copy
from app.services.overview_service import (
    SOURCE_GROUP_SOCIAL,
    _is_real_transport_complaint,
    _matches_source_group,
    _sort_transport_clusters,
    _telemetry_only,
)

MALAYSIA_BOUNDS = {"south": 0.85, "north": 7.5, "west": 99.0, "east": 119.5}
KV_BOUNDS = {"south": 2.85, "north": 3.45, "west": 101.35, "east": 101.85}
KV_CENTER = {"lat": 3.139, "lon": 101.687}

ROUTE_SHORT_TO_LINE = {
    "KJL": "kelana-jaya",
    "AGL": "ampang-sri-petaling",
    "SPL": "ampang-sri-petaling",
    "KGL": "kajang",
    "PYL": "putrajaya",
    "MRL": "monorail",
}

_REPORT_COLORS = {
    "disruption": "#f87171",
    "delay": "#fb923c",
    "minor": "#fbbf24",
    "normal": "#c2410c",
}


def _in_malaysia(lat: float, lon: float) -> bool:
    return (
        MALAYSIA_BOUNDS["south"] <= lat <= MALAYSIA_BOUNDS["north"]
        and MALAYSIA_BOUNDS["west"] <= lon <= MALAYSIA_BOUNDS["east"]
    )


@lru_cache(maxsize=1)
def _load_rail_lines() -> dict:
    path = Path(__file__).resolve().parents[2] / "static" / "data" / "rail-lines.json"
    if not path.exists():
        return {"type": "FeatureCollection", "scope": "malaysia", "features": []}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=2)
def _bus_stops_from_gtfs(*, limit: int = 100) -> list[dict]:
    """Key Rapid KL bus stops from official GTFS — Malaysia coordinates only."""
    from app.collectors.gtfs.static_client import download_static

    try:
        path = download_static("rapid-bus-kl")
    except OSError:
        return []
    seen: set[str] = set()
    stops: list[dict] = []
    with zipfile.ZipFile(path) as zf:
        for row in csv.DictReader(io.TextIOWrapper(zf.open("stops.txt"), encoding="utf-8-sig")):
            if not row.get("stop_lat") or not row.get("stop_lon"):
                continue
            lat = float(row["stop_lat"])
            lon = float(row["stop_lon"])
            if not _in_malaysia(lat, lon):
                continue
            name = (row.get("stop_name") or row["stop_id"]).title()
            key = _normalise(name)
            if key in seen:
                continue
            seen.add(key)
            stops.append(
                {
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "mode": "bus",
                    "lines": ["Rapid KL Bus"],
                    "status": "normal",
                }
            )
            if len(stops) >= limit:
                break
    stops.sort(key=lambda row: row["name"])
    return stops


def get_rail_lines_geojson() -> dict:
    return _load_rail_lines()


def get_map_stations(*, limit: int = 120, layer: str = "rail") -> dict:
    """Malaysia rail/bus markers from GTFS + active disruption hints."""
    if layer == "bus":
        return {
            "product": "TrafficMY",
            "scope": "malaysia",
            "layer": "bus",
            "bounds": MALAYSIA_BOUNDS,
            "kv_bounds": KV_BOUNDS,
            "center": KV_CENTER,
            "stations": _bus_stops_from_gtfs(limit=min(limit, 100)),
            "rail_lines": _load_rail_lines(),
            "bus_layer": {"available": True, "label": "Up to 100 Rapid KL bus stops from official GTFS."},
            "rail_lines_tracked": len([spec for spec in LINE_CATALOG if spec.get("mode") == "rail"]),
        }

    graph = _graph()
    board = get_line_status_board()
    incident_locations: set[str] = set()
    for cluster in board.get("recent_reports") or []:
        loc = (cluster.get("location") or "").lower()
        if loc:
            incident_locations.add(loc)
        line_id = match_transport_line(cluster)
        if line_id:
            incident_locations.add(line_id)

    seen: set[str] = set()
    stations: list[dict] = []
    for normalised, stop_ids in graph["names"].items():
        if normalised in seen:
            continue
        seen.add(normalised)
        stop = graph["stops"][stop_ids[0]]
        lat, lon = stop["lat"], stop["lon"]
        if not _in_malaysia(lat, lon):
            continue
        route_ids = sorted({graph["stops"][sid].get("route_id", "") for sid in stop_ids if graph["stops"][sid].get("route_id")})
        line_ids: list[str] = []
        line_labels: list[str] = []
        for rid in route_ids:
            if rid in ROUTE_SHORT_TO_LINE:
                lid = ROUTE_SHORT_TO_LINE[rid]
                if lid not in line_ids:
                    line_ids.append(lid)
            label = graph["routes"].get(rid, {}).get("short_name", rid)
            if label and label not in line_labels:
                line_labels.append(label)
        label = stop["name"]
        has_incident = any(
            needle in label.lower() or label.lower() in needle for needle in incident_locations
        )
        worst_status = "normal"
        for line in board["lines"]:
            if line["status"] in {"minor", "delay", "disruption"} and any(
                token in (line.get("reason") or "").lower() + line["name"].lower() for token in [label.lower()]
            ):
                has_incident = True
                if line["status"] == "disruption":
                    worst_status = "disruption"
                elif line["status"] == "delay" and worst_status != "disruption":
                    worst_status = "delay"
                elif worst_status == "normal":
                    worst_status = "minor"
        stations.append(
            {
                "name": label,
                "lat": lat,
                "lon": lon,
                "lines": line_labels[:4],
                "line_ids": line_ids,
                "status": worst_status if has_incident else "normal",
                "mode": "rail",
            }
        )
        if len(stations) >= limit:
            break

    stations.sort(key=lambda row: row["name"])
    return {
        "product": "TrafficMY",
        "scope": "malaysia",
        "layer": "rail",
        "bounds": MALAYSIA_BOUNDS,
        "kv_bounds": KV_BOUNDS,
        "center": KV_CENTER,
        "stations": stations,
        "rail_lines": _load_rail_lines(),
        "bus_layer": {
            "available": True,
            "label": "Bus stops from Rapid KL GTFS (toggle Bus layer).",
        },
        "rail_lines_tracked": len([spec for spec in LINE_CATALOG if spec.get("mode") == "rail"]),
    }


def get_station_detail(name: str) -> dict | None:
    """Lines serving a station + nearest report from the status board."""
    needle = _normalise(name)
    if not needle:
        return None
    graph = _graph()
    stop_ids = graph["names"].get(needle)
    if not stop_ids:
        for key, ids in graph["names"].items():
            if needle in key or key in needle:
                stop_ids = ids
                needle = key
                break
    if not stop_ids:
        return None
    stop = graph["stops"][stop_ids[0]]
    if not _in_malaysia(stop["lat"], stop["lon"]):
        return None
    route_ids = sorted({graph["stops"][sid].get("route_id", "") for sid in stop_ids if graph["stops"][sid].get("route_id")})
    line_ids: list[str] = []
    line_names: list[str] = []
    for rid in route_ids:
        if rid in ROUTE_SHORT_TO_LINE:
            lid = ROUTE_SHORT_TO_LINE[rid]
            if lid not in line_ids:
                line_ids.append(lid)
        spec = next((s for s in LINE_CATALOG if s["id"] == ROUTE_SHORT_TO_LINE.get(rid)), None)
        if spec and spec["name"] not in line_names:
            line_names.append(spec["name"])
        elif rid:
            short = graph["routes"].get(rid, {}).get("short_name", rid)
            if short not in line_names:
                line_names.append(short)

    board = get_line_status_board()
    line_status = {line["id"]: line for line in board["lines"]}
    serving = [
        {
            "id": lid,
            "name": line_status[lid]["name"] if lid in line_status else lid,
            "status": line_status[lid]["status"] if lid in line_status else "unknown",
            "status_label": line_status[lid]["status_label"] if lid in line_status else "No data",
            "color": LINE_COLORS.get(lid, "#64748b"),
        }
        for lid in line_ids
    ]

    station_label = stop["name"]
    nearest_report = None
    for cluster in board.get("recent_reports") or []:
        blob = " ".join(
            [
                cluster.get("location") or "",
                cluster.get("entity") or "",
                cluster.get("example_text") or "",
            ]
        ).lower()
        if station_label.lower() in blob or needle in blob:
            public_copy = public_incident_copy(cluster)
            nearest_report = {
                "cluster_id": cluster.get("cluster_id"),
                "entity": cluster.get("entity"),
                "headline": public_copy["headline"],
                "summary": public_copy["summary"],
                "last_seen_at": cluster.get("last_seen_at"),
            }
            break

    return {
        "name": station_label,
        "lat": stop["lat"],
        "lon": stop["lon"],
        "lines": serving,
        "line_names": line_names,
        "nearest_report": nearest_report,
        "scope": "malaysia",
    }


def _cluster_coordinates(cluster: dict, graph: dict) -> tuple[float, float] | None:
    """Map a crowd cluster to GTFS station coords when possible."""
    needles = [cluster.get("location") or "", cluster.get("entity") or ""]
    for needle in needles:
        key = _normalise(needle)
        if not key:
            continue
        if key in graph["names"]:
            stop = graph["stops"][graph["names"][key][0]]
            return stop["lat"], stop["lon"]
        for name_key, stop_ids in graph["names"].items():
            if key in name_key or name_key in key:
                stop = graph["stops"][stop_ids[0]]
                return stop["lat"], stop["lon"]
    return None


def _cluster_pin_status(cluster: dict) -> str:
    sev = cluster.get("severity", "low")
    text = (cluster.get("example_text") or "").lower()
    if sev == "high" or any(t in text for t in ["gangguan", "suspend", "no service", "terhenti"]):
        return "disruption"
    if sev == "medium" or any(t in text for t in ["delay", "lambat", "kelewatan", "stuck", "penuh"]):
        return "delay"
    return "minor"


def _community_report_pins(*, limit: int = 80) -> list[dict]:
    """Threads-first crowd pins — social sources only, Malaysia transport."""
    clusters = list_clusters(category="transport")
    clusters = [c for c in clusters if _matches_source_group(c, "social")]
    clusters = [c for c in clusters if not _telemetry_only(c)]
    clusters = [c for c in clusters if _is_real_transport_complaint(c)]
    clusters = [c for c in clusters if is_inside_myt_today(c.get("last_seen_at") or c.get("first_seen_at"))]
    clusters = _sort_transport_clusters(clusters, sort_by="freshest")
    graph = _graph()
    pins: list[dict] = []
    seen: set[str] = set()
    for cluster in clusters:
        if cluster.get("subcategory") == "line_info":
            continue
        coords = _cluster_coordinates(cluster, graph)
        if not coords:
            continue
        lat, lon = coords
        if not _in_malaysia(lat, lon):
            continue
        key = f"{lat:.4f},{lon:.4f}:{cluster.get('cluster_id', '')}"
        if key in seen:
            continue
        seen.add(key)
        status = _cluster_pin_status(cluster)
        line_id = match_transport_line(cluster)
        sources = cluster.get("sources") or ""
        public_copy = public_incident_copy(cluster)
        pins.append(
            {
                "cluster_id": cluster.get("cluster_id"),
                "lat": lat,
                "lon": lon,
                "status": status,
                "severity": status,
                "color": _REPORT_COLORS.get(status, _REPORT_COLORS["minor"]),
                "entity": cluster.get("entity") or "",
                "location": cluster.get("location") or "",
                "line_id": line_id,
                "headline": public_copy["headline"],
                "summary": public_copy["summary"],
                "example_url": cluster.get("example_url") or "",
                "sources": sources,
                "primary": "threads" in sources,
                "last_seen_at": cluster.get("last_seen_at"),
                "confidence_band": cluster.get("confidence_band"),
                "source_type": "community",
            }
        )
        if len(pins) >= limit:
            break
    return pins


def _interchange_map_pins(*, limit: int = 40) -> list[dict]:
    """Interchange stations with GTFS coordinates and transfer line details."""
    from app.services.line_reference_service import get_all_interchanges

    graph = _graph()
    pins: list[dict] = []
    for hub in get_all_interchanges().get("hubs") or []:
        station = hub.get("station") or ""
        needle = _normalise(station)
        if not needle:
            continue
        stop_ids = graph["names"].get(needle)
        if not stop_ids:
            for name_key, ids in graph["names"].items():
                if needle in name_key or name_key in needle:
                    stop_ids = ids
                    break
        if not stop_ids:
            continue
        stop = graph["stops"][stop_ids[0]]
        lat, lon = stop["lat"], stop["lon"]
        if not _in_malaysia(lat, lon):
            continue
        transfers: list[dict] = []
        for conn in hub.get("connections") or []:
            targets = conn.get("connects_to_line_ids") or []
            transfers.append(
                {
                    "from_line_id": conn.get("from_line_id"),
                    "from_line_name": conn.get("from_line_name"),
                    "connects_to": conn.get("connects_to"),
                    "connects_to_line_ids": targets,
                    "line_colours": conn.get("line_colours") or [],
                    "walking_note": conn.get("walking_note") or "",
                }
            )
        line_labels = []
        for lid in hub.get("lines") or []:
            spec = next((s for s in LINE_CATALOG if s["id"] == lid), None)
            if spec:
                line_labels.append({"id": lid, "name": spec["name"], "color": LINE_COLORS.get(lid, "#64748b")})
        pins.append(
            {
                "station": station,
                "lat": lat,
                "lon": lon,
                "lines": hub.get("lines") or [],
                "line_labels": line_labels,
                "transfers": transfers,
            }
        )
        if len(pins) >= limit:
            break
    return pins


def get_live_map(
    *,
    include_vehicles: bool = False,
    vehicle_limit: int = 60,
    report_limit: int = 80,
) -> dict:
    """Hybrid map payload — community reports first, optional GTFS-RT buses & trains."""
    reports = _community_report_pins(limit=report_limit)
    interchanges = _interchange_map_pins()
    vehicles: list[dict] = []
    if include_vehicles:
        from app.collectors.gtfs.rt_client import fetch_bus_vehicle_positions, fetch_rail_vehicle_positions

        bus_vehicles = fetch_bus_vehicle_positions(limit=vehicle_limit)
        rail_vehicles = fetch_rail_vehicle_positions(limit=30)
        # Mark bus mode explicitly if not present
        for bv in bus_vehicles:
            if "mode" not in bv:
                bv["mode"] = "bus"
        vehicles = rail_vehicles + bus_vehicles
    return {
        "product": "TrafficMY",
        "scope": "malaysia",
        "primary_source": "community",
        "philosophy": "Threads-first — rider reports drive the map; GTFS bus & train GPS is optional background.",
        "bounds": MALAYSIA_BOUNDS,
        "kv_bounds": KV_BOUNDS,
        "center": KV_CENTER,
        "fetched_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "reports": reports,
        "interchanges": interchanges,
        "vehicles": vehicles,
        "rail_lines": _load_rail_lines(),
        "counts": {
            "reports": len(reports),
            "interchanges": len(interchanges),
            "vehicles": len(vehicles),
        },
        "disclaimers": {
            "reports": "Crowd reports from Threads/Reddit — not official operator status.",
            "vehicles": "Official GPS from data.gov.my — may lag or drop off-network.",
            "rail": "Rail lines are reference geometry. Live train positions are shown for KTMB.",
        },
    }
