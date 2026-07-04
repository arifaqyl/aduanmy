"""Snap GTFS stop coordinates onto committed rail line geometry."""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Iterable

_EARTH_RADIUS_M = 6_371_000.0
_RAIL_LINES_PATH = Path(__file__).resolve().parents[2] / "static" / "data" / "rail-lines.json"


def _deg_to_rad(value: float) -> float:
    return value * math.pi / 180.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    dlat = _deg_to_rad(lat2 - lat1)
    dlon = _deg_to_rad(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(_deg_to_rad(lat1)) * math.cos(_deg_to_rad(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def _nearest_on_segment(
    lat: float,
    lon: float,
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> tuple[float, float, float]:
    """Return snapped lat/lon on segment and distance in metres."""
    x, y = lon, lat
    x1, y1 = lon1, lat1
    x2, y2 = lon2, lat2
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        dist = haversine_m(lat, lon, lat1, lon1)
        return lat1, lon1, dist
    t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    snap_lon = x1 + t * dx
    snap_lat = y1 + t * dy
    return snap_lat, snap_lon, haversine_m(lat, lon, snap_lat, snap_lon)


def nearest_point_on_linestring(
    lat: float,
    lon: float,
    coordinates: list[list[float]],
) -> tuple[float, float, float]:
    best_lat, best_lon, best_dist = lat, lon, float("inf")
    for idx in range(len(coordinates) - 1):
        lon1, lat1 = coordinates[idx]
        lon2, lat2 = coordinates[idx + 1]
        snap_lat, snap_lon, dist = _nearest_on_segment(lat, lon, lat1, lon1, lat2, lon2)
        if dist < best_dist:
            best_lat, best_lon, best_dist = snap_lat, snap_lon, dist
    return best_lat, best_lon, best_dist


@lru_cache(maxsize=1)
def _line_geometries_by_id() -> dict[str, list[list[list[float]]]]:
    grouped: dict[str, list[list[list[float]]]] = {}
    if not _RAIL_LINES_PATH.exists():
        return grouped
    payload = json.loads(_RAIL_LINES_PATH.read_text(encoding="utf-8"))
    for feature in payload.get("features") or []:
        line_id = (feature.get("properties") or {}).get("line_id")
        geometry = feature.get("geometry") or {}
        if not line_id or geometry.get("type") != "LineString":
            continue
        coords = geometry.get("coordinates") or []
        if len(coords) >= 2:
            grouped.setdefault(line_id, []).append(coords)
    return grouped


def snap_coords_to_lines(
    lat: float,
    lon: float,
    line_ids: Iterable[str] | None = None,
    *,
    max_snap_m: float = 2500.0,
) -> tuple[float, float]:
    """Project a stop onto the nearest committed rail polyline."""
    grouped = _line_geometries_by_id()
    candidates = list(line_ids) if line_ids else list(grouped.keys())
    if not candidates:
        return lat, lon

    best_lat, best_lon, best_dist = lat, lon, float("inf")
    for line_id in candidates:
        for coords in grouped.get(line_id, []):
            snap_lat, snap_lon, dist = nearest_point_on_linestring(lat, lon, coords)
            if dist < best_dist:
                best_lat, best_lon, best_dist = snap_lat, snap_lon, dist

    if best_dist > max_snap_m:
        return lat, lon
    return best_lat, best_lon
