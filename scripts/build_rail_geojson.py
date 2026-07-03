#!/usr/bin/env python3
"""Build rail-lines.json from official Prasarana GTFS shapes (rapid-rail-kl).

Removes hand-drawn approximate geometry (e.g. KTM loop) that rendered as circles.

Usage:
    python scripts/build_rail_geojson.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "data" / "rail-lines.json"

ROUTE_CONFIG: dict[str, dict] = {
    "KJ": {
        "line_id": "kelana-jaya",
        "network": "lrt",
        "name": "LRT Kelana Jaya Line",
        "color": "#e31837",
    },
    "AG": {
        "line_id": "ampang-sri-petaling",
        "network": "lrt",
        "name": "LRT Ampang Line",
        "branch": "Ampang",
        "color": "#f7941d",
    },
    "PH": {
        "line_id": "ampang-sri-petaling",
        "network": "lrt",
        "name": "LRT Sri Petaling Line",
        "branch": "Sri Petaling",
        "color": "#f7941d",
    },
    "KGL": {
        "line_id": "kajang",
        "network": "mrt",
        "name": "MRT Kajang Line",
        "color": "#007a33",
    },
    "PYL": {
        "line_id": "putrajaya",
        "network": "mrt",
        "name": "MRT Putrajaya Line",
        "color": "#f4c300",
    },
    "MR": {
        "line_id": "monorail",
        "network": "monorail",
        "name": "KL Monorail Line",
        "color": "#8dc63f",
    },
}


def _load_shapes(zf: zipfile.ZipFile) -> dict[str, list[tuple[float, float]]]:
    by_id: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    for row in csv.DictReader(io.TextIOWrapper(zf.open("shapes.txt"), encoding="utf-8-sig")):
        by_id[row["shape_id"]].append(
            (int(row["shape_pt_sequence"]), float(row["shape_pt_lon"]), float(row["shape_pt_lat"]))
        )
    out: dict[str, list[tuple[float, float]]] = {}
    for shape_id, pts in by_id.items():
        pts.sort(key=lambda p: p[0])
        out[shape_id] = [(lon, lat) for _, lon, lat in pts]
    return out


def _primary_shape_id(trips: list[dict], route_id: str) -> str | None:
    counts: Counter[str] = Counter()
    for trip in trips:
        if trip.get("route_id") != route_id:
            continue
        shape_id = (trip.get("shape_id") or "").strip()
        if shape_id:
            counts[shape_id] += 1
    if not counts:
        return None
    # Prefer direction _0 shapes (consistent with operator exports).
    candidates = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    for shape_id, _ in candidates:
        if shape_id.endswith("_0"):
            return shape_id
    return candidates[0][0]


def build_from_gtfs(gtfs_path: Path) -> dict:
    with zipfile.ZipFile(gtfs_path) as zf:
        shapes = _load_shapes(zf)
        trips = list(csv.DictReader(io.TextIOWrapper(zf.open("trips.txt"), encoding="utf-8-sig")))
        routes = {
            row["route_id"]: row
            for row in csv.DictReader(io.TextIOWrapper(zf.open("routes.txt"), encoding="utf-8-sig"))
        }

    features: list[dict] = []
    for route_id, cfg in ROUTE_CONFIG.items():
        if route_id not in routes:
            continue
        shape_id = _primary_shape_id(trips, route_id)
        if not shape_id or shape_id not in shapes:
            continue
        coords = shapes[shape_id]
        if len(coords) < 2:
            continue
        route_row = routes[route_id]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "line_id": cfg["line_id"],
                    "route_id": route_id,
                    "network": cfg["network"],
                    "name": cfg["name"],
                    "branch": cfg.get("branch") or route_row.get("route_short_name", route_id),
                    "color": cfg["color"],
                    "source": "gtfs-shapes",
                    "shape_id": shape_id,
                },
                "geometry": {"type": "LineString", "coordinates": coords},
            }
        )

    return {
        "type": "FeatureCollection",
        "scope": "malaysia",
        "source": "Prasarana rapid-rail-kl GTFS shapes (data.gov.my)",
        "note": "KTM Komuter and LRT3 omitted until official GTFS shapes are available.",
        "features": features,
    }


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from app.collectors.gtfs.static_client import download_static

    path = download_static("rapid-rail-kl")
    geojson = build_from_gtfs(path)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(geojson, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(geojson['features'])} features)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
