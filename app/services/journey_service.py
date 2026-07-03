from __future__ import annotations

import csv
import heapq
import io
import math
import threading
import time
import zipfile
from functools import lru_cache
from pathlib import Path

import requests

from app.collectors.gtfs.static_client import download_static

WALKING_METRES_PER_MINUTE = 80
TRANSFER_RADIUS_METRES = 450
GEOCODER_URL = "https://nominatim.openstreetmap.org/search"

ROUTE_FRIENDLY_NAMES = {
    "KJL": "Kelana Jaya Line",
    "SPL": "Ampang / Sri Petaling Line",
    "AGL": "Ampang Line",
    "SPG": "Sri Petaling Line",
    "PYL": "MRT Putrajaya Line",
    "KGL": "MRT Kajang Line",
    "MRL": "KL Monorail",
    "BRT": "BRT Sunway Line",
}


def _route_display_name(route: dict, route_id: str) -> str:
    short = route.get("short_name") or route_id
    name = route.get("name") or short
    if short in ROUTE_FRIENDLY_NAMES:
        return ROUTE_FRIENDLY_NAMES[short]
    if name in {short, route_id} and len(name) <= 4:
        return ROUTE_FRIENDLY_NAMES.get(short, name)
    return name

_graph_lock = threading.Lock()
_graph_cache: tuple[float, dict] | None = None
_geocoder_lock = threading.Lock()
_last_geocoder_request = 0.0


def _normalise(value: str) -> str:
    return " ".join(value.lower().replace("-", " ").split())


def _minutes(value: str) -> float:
    parts = value.split(":")
    if len(parts) != 3:
        return 0
    return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60


def _distance_metres(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    radius = 6_371_000
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    dp = math.radians(b_lat - a_lat)
    dl = math.radians(b_lon - a_lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))


def _read_csv(zf: zipfile.ZipFile, name: str) -> list[dict]:
    return list(csv.DictReader(io.TextIOWrapper(zf.open(name), encoding="utf-8-sig")))


def _build_graph(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        stops_raw = _read_csv(zf, "stops.txt")
        routes_raw = _read_csv(zf, "routes.txt")
        stop_times_raw = _read_csv(zf, "stop_times.txt")

    routes = {
        row["route_id"]: {
            "id": row["route_id"],
            "name": row.get("route_long_name") or row.get("route_short_name") or row["route_id"],
            "short_name": row.get("route_short_name") or row["route_id"],
            "color": f"#{(row.get('route_color') or '64748b').lstrip('#')}",
        }
        for row in routes_raw
        if row.get("route_id")
    }
    stops = {
        row["stop_id"]: {
            "id": row["stop_id"],
            "name": (row.get("stop_name") or row["stop_id"]).title(),
            "lat": float(row["stop_lat"]),
            "lon": float(row["stop_lon"]),
            "route_id": row.get("route_id", ""),
            "accessible": str(row.get("isOKU", "")).lower() == "true",
        }
        for row in stops_raw
        if row.get("stop_id") and row.get("stop_lat") and row.get("stop_lon")
    }
    adjacency: dict[str, dict[str, dict]] = {stop_id: {} for stop_id in stops}
    trips: dict[str, list[dict]] = {}
    for row in stop_times_raw:
        if row.get("stop_id") not in stops:
            continue
        trips.setdefault(row.get("trip_id", ""), []).append(row)

    for rows in trips.values():
        rows.sort(key=lambda row: int(row.get("stop_sequence") or 0))
        for left, right in zip(rows, rows[1:]):
            a, b = left["stop_id"], right["stop_id"]
            route_id = left.get("route_id") or stops[a].get("route_id", "")
            duration = _minutes(right.get("arrival_time", "")) - _minutes(left.get("departure_time", ""))
            duration = max(1.0, min(duration or 2.0, 15.0))
            existing = adjacency[a].get(b)
            if not existing or duration < existing["minutes"]:
                adjacency[a][b] = {"minutes": duration, "kind": "ride", "route_id": route_id}

    stop_list = list(stops.values())
    for index, left in enumerate(stop_list):
        for right in stop_list[index + 1 :]:
            if left["route_id"] == right["route_id"]:
                continue
            distance = _distance_metres(left["lat"], left["lon"], right["lat"], right["lon"])
            same_name = _normalise(left["name"]) == _normalise(right["name"])
            if not same_name and distance > TRANSFER_RADIUS_METRES:
                continue
            walk_minutes = max(3, math.ceil(distance / WALKING_METRES_PER_MINUTE) + 2)
            edge = {"minutes": walk_minutes, "kind": "transfer", "distance_metres": round(distance)}
            adjacency[left["id"]][right["id"]] = edge
            adjacency[right["id"]][left["id"]] = edge

    names: dict[str, list[str]] = {}
    for stop in stops.values():
        names.setdefault(_normalise(stop["name"]), []).append(stop["id"])
    return {"stops": stops, "routes": routes, "adjacency": adjacency, "names": names}


def _graph() -> dict:
    global _graph_cache
    path = download_static("rapid-rail-kl")
    mtime = path.stat().st_mtime
    if _graph_cache and _graph_cache[0] == mtime:
        return _graph_cache[1]
    with _graph_lock:
        if _graph_cache and _graph_cache[0] == mtime:
            return _graph_cache[1]
        built = _build_graph(path)
        _graph_cache = (mtime, built)
        return built


def list_rail_stations(query: str = "", *, limit: int = 12) -> list[dict]:
    graph = _graph()
    needle = _normalise(query)
    out = []
    for normalised, stop_ids in graph["names"].items():
        if needle and needle not in normalised:
            continue
        rows = [graph["stops"][stop_id] for stop_id in stop_ids]
        route_ids = sorted({row["route_id"] for row in rows if row["route_id"]})
        out.append(
            {
                "name": rows[0]["name"],
                "lat": rows[0]["lat"],
                "lon": rows[0]["lon"],
                "lines": [graph["routes"].get(route_id, {"short_name": route_id})["short_name"] for route_id in route_ids],
                "accessible": all(row["accessible"] for row in rows),
            }
        )
    out.sort(key=lambda row: (not _normalise(row["name"]).startswith(needle), row["name"]))
    return out[:limit]


@lru_cache(maxsize=256)
def _geocode(query: str) -> dict | None:
    global _last_geocoder_request
    with _geocoder_lock:
        wait = 1.0 - (time.monotonic() - _last_geocoder_request)
        if wait > 0:
            time.sleep(wait)
        response = requests.get(
            GEOCODER_URL,
            params={"q": query, "format": "jsonv2", "countrycodes": "my", "limit": 1},
            headers={"User-Agent": "TrafficMY/0.3 (hello@arifaqyl.me)"},
            timeout=12,
        )
        _last_geocoder_request = time.monotonic()
    response.raise_for_status()
    items = response.json()
    if not items:
        return None
    return {
        "label": items[0].get("display_name") or query,
        "lat": float(items[0]["lat"]),
        "lon": float(items[0]["lon"]),
        "source": "OpenStreetMap Nominatim",
    }


def _resolve_place(value: str, graph: dict) -> dict | None:
    if value.startswith("@"):
        try:
            lat_text, lon_text = value[1:].split(",", 1)
            place = {"label": "Current location", "lat": float(lat_text), "lon": float(lon_text), "source": "browser"}
        except (ValueError, TypeError):
            return None
        nearest = min(
            graph["stops"].values(),
            key=lambda stop: _distance_metres(place["lat"], place["lon"], stop["lat"], stop["lon"]),
        )
        distance = _distance_metres(place["lat"], place["lon"], nearest["lat"], nearest["lon"]) * 1.2
        return {
            **place,
            "station_ids": graph["names"][_normalise(nearest["name"])],
            "station": nearest["name"],
            "walk_metres": round(distance),
        }
    key = _normalise(value)
    stop_ids = graph["names"].get(key)
    if stop_ids:
        stop = graph["stops"][stop_ids[0]]
        return {"label": stop["name"], "lat": stop["lat"], "lon": stop["lon"], "station_ids": stop_ids, "walk_metres": 0}
    candidates = list_rail_stations(value, limit=1)
    if candidates and key in _normalise(candidates[0]["name"]):
        matched_ids = graph["names"][_normalise(candidates[0]["name"])]
        return {**candidates[0], "label": candidates[0]["name"], "station_ids": matched_ids, "walk_metres": 0}
    place = _geocode(value)
    if not place:
        return None
    nearest = min(
        graph["stops"].values(),
        key=lambda stop: _distance_metres(place["lat"], place["lon"], stop["lat"], stop["lon"]),
    )
    distance = _distance_metres(place["lat"], place["lon"], nearest["lat"], nearest["lon"]) * 1.2
    station_ids = graph["names"][_normalise(nearest["name"])]
    return {**place, "station_ids": station_ids, "station": nearest["name"], "walk_metres": round(distance)}


def _shortest_path(graph: dict, starts: list[str], targets: set[str]) -> tuple[float, list[tuple[str, str, dict]]] | None:
    queue = [(0.0, stop_id) for stop_id in starts]
    heapq.heapify(queue)
    distances = {stop_id: 0.0 for stop_id in starts}
    previous: dict[str, tuple[str, dict]] = {}
    found = None
    while queue:
        total, current = heapq.heappop(queue)
        if total != distances.get(current):
            continue
        if current in targets:
            found = current
            break
        for neighbour, edge in graph["adjacency"].get(current, {}).items():
            candidate = total + edge["minutes"]
            if candidate >= distances.get(neighbour, float("inf")):
                continue
            distances[neighbour] = candidate
            previous[neighbour] = (current, edge)
            heapq.heappush(queue, (candidate, neighbour))
    if not found:
        return None
    edges: list[tuple[str, str, dict]] = []
    cursor = found
    while cursor not in starts:
        parent, edge = previous[cursor]
        edges.append((parent, cursor, edge))
        cursor = parent
    edges.reverse()
    return distances[found], edges


def _legs(graph: dict, edges: list[tuple[str, str, dict]]) -> list[dict]:
    legs: list[dict] = []
    for start_id, end_id, edge in edges:
        start, end = graph["stops"][start_id], graph["stops"][end_id]
        route_id = edge.get("route_id", "")
        if edge["kind"] == "ride" and legs and legs[-1]["kind"] == "ride" and legs[-1]["route_id"] == route_id:
            legs[-1]["to"] = end["name"]
            legs[-1]["minutes"] += edge["minutes"]
            legs[-1]["stops"] += 1
            continue
        if edge["kind"] == "ride":
            route = graph["routes"].get(route_id, {"name": route_id, "short_name": route_id, "color": "#64748b"})
            legs.append(
                {
                    "kind": "ride",
                    "route_id": route_id,
                    "line": _route_display_name(route, route_id),
                    "short_name": route["short_name"],
                    "color": route["color"],
                    "from": start["name"],
                    "to": end["name"],
                    "minutes": edge["minutes"],
                    "stops": 1,
                }
            )
        else:
            legs.append(
                {
                    "kind": "transfer",
                    "from": start["name"],
                    "to": end["name"],
                    "minutes": edge["minutes"],
                    "distance_metres": edge.get("distance_metres", 0),
                }
            )
    for leg in legs:
        leg["minutes"] = max(1, round(leg["minutes"]))
    return legs


def plan_rail_journey(origin: str, destination: str) -> dict:
    graph = _graph()
    start = _resolve_place(origin, graph)
    end = _resolve_place(destination, graph)
    if not start or not end:
        missing = origin if not start else destination
        raise ValueError(f"Could not find {missing} in Malaysia")
    result = _shortest_path(graph, start["station_ids"], set(end["station_ids"]))
    if not result:
        raise ValueError("No rail route found between those places")
    rail_minutes, edges = result
    start_walk = math.ceil(start.get("walk_metres", 0) / WALKING_METRES_PER_MINUTE)
    end_walk = math.ceil(end.get("walk_metres", 0) / WALKING_METRES_PER_MINUTE)
    legs = _legs(graph, edges)
    return {
        "origin": {
            "label": start["label"],
            "station": graph["stops"][start["station_ids"][0]]["name"],
            "walk_metres": start.get("walk_metres", 0),
            "walk_minutes": start_walk,
        },
        "destination": {
            "label": end["label"],
            "station": graph["stops"][end["station_ids"][0]]["name"],
            "walk_metres": end.get("walk_metres", 0),
            "walk_minutes": end_walk,
        },
        "rail_minutes": round(rail_minutes),
        "total_minutes": round(rail_minutes) + start_walk + end_walk,
        "transfers": sum(1 for leg in legs if leg["kind"] == "transfer"),
        "legs": legs,
        "data_source": "Malaysia government GTFS static feed",
        "walking_note": "Walking distance is a straight-line estimate with a 20% street factor, not turn-by-turn navigation.",
        "mixed_mode_url": "https://myrapid.com.my/journey-planner/",
    }
