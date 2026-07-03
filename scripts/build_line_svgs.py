#!/usr/bin/env python3
"""Compose transit schematics from reusable OSS marker components.

Patterns from public-transport/generating-transit-maps (station list + line colours +
even spacing). Markers in static/assets/markers/. Original Malaysia geometry only.

Usage:
    python scripts/build_line_svgs.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIONS_PATH = ROOT / "static" / "data" / "line-stations.json"
REFERENCE_PATH = ROOT / "static" / "data" / "lines-reference.json"
MARKERS_DIR = ROOT / "static" / "assets" / "markers"
SCHEMATICS_DIR = ROOT / "static" / "assets" / "schematics"
LINES_DIR = ROOT / "static" / "lines"
DATA_DIR = ROOT / "static" / "data"

FONT = "IBM Plex Sans,sans-serif"
BG = "#111318"
TEXT = "#9a958c"
TEXT_DIM = "#6b6660"
TEXT_HI = "#ece8e1"
LINE_W = 6
GAP = 36
PAD_X = 28
LABEL_Y_OFFSET = 24
VERTICAL_THRESHOLD = 15
ROW_H = 24

# Aliases for schematic filenames (user-facing names).
LINE_ALIASES = {
    "lrt3": "lrt3-shah-alam",
    "kajang": "kajang-mrt",
    "putrajaya": "putrajaya-mrt",
}


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _load_marker(name: str) -> str:
    path = MARKERS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Missing marker component: {path}")
    return path.read_text(encoding="utf-8").strip()


def _marker_at(marker_svg: str, x: float, y: float, *, colour: str, bg: str = BG) -> str:
    inner = marker_svg.replace("currentColor", colour).replace("var(--schem-bg, #111318)", bg)
    return f'<g transform="translate({x:.1f},{y:.1f})">{inner}</g>'


def _station_xy(index: int, count: int, *, y: float = 48) -> tuple[float, float]:
    if count <= 1:
        return float(PAD_X), y
    x = PAD_X + index * GAP if count > 1 else (PAD_X * 2) / 2
    return float(x), y


def _view_width(count: int) -> int:
    return int(PAD_X * 2 + max(count - 1, 0) * GAP)


def _node_svg(x: float, y: float, station: dict, colour: str) -> str:
    stop = _load_marker("stop-dot.svg")
    ix = _load_marker("interchange-ring.svg")
    term = _load_marker("terminal-square.svg")
    if station.get("terminal"):
        c = colour if station.get("highlight") else TEXT_HI
        return _marker_at(term, x, y, colour=c)
    if station.get("interchange"):
        c = colour if station.get("highlight") else TEXT_HI
        return _marker_at(ix, x, y, colour=c)
    return _marker_at(stop, x, y, colour=TEXT_HI)


def _label_svg(x: float, y: float, station: dict, *, show_all: bool) -> str:
    name = station.get("abbr") or station.get("name", "")
    if not show_all and not (
        station.get("terminal") or station.get("interchange") or station.get("highlight")
    ):
        return ""
    fs = 11 if len(name) > 10 else 12
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" fill="{TEXT}" font-size="{fs}" '
        f'font-family="{FONT}" text-anchor="middle">{_esc(name)}</text>'
    )


def _vertical_node(x: float, y: float, station: dict, colour: str) -> str:
    term = _load_marker("terminal-square.svg")
    ix = _load_marker("interchange-ring.svg")
    if station.get("terminal"):
        c = colour if station.get("highlight") else TEXT_HI
        return _marker_at(term, x, y, colour=c)
    if station.get("interchange"):
        c = colour if station.get("highlight") else TEXT_HI
        return _marker_at(ix, x, y, colour=c)
    return f'<line x1="{x - 5:.1f}" y1="{y:.1f}" x2="{x + 5:.1f}" y2="{y:.1f}" stroke="{TEXT_HI}" stroke-width="2"/>'


def _vertical_diagram(name: str, colour: str, stations: list[dict]) -> str:
    count = len(stations)
    line_x = 36.0
    label_x = 52.0
    pad_y = 28.0
    height = int(pad_y * 2 + max(count - 1, 0) * ROW_H)
    width = 240
    y0 = pad_y
    y1 = pad_y + (count - 1) * ROW_H
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{_esc(name)} schematic">',
        f"<title>{_esc(name)}</title>",
        f'<rect width="{width}" height="{height}" fill="{BG}"/>',
        f'<line x1="{line_x:.1f}" y1="{y0:.1f}" x2="{line_x:.1f}" y2="{y1:.1f}" '
        f'stroke="{colour}" stroke-width="{LINE_W}" stroke-linecap="butt"/>',
    ]
    for i, st in enumerate(stations):
        y = pad_y + i * ROW_H
        parts.append(_vertical_node(line_x, y, st, colour))
        label = st.get("abbr") or st.get("name", "")
        weight = "600" if st.get("interchange") or st.get("terminal") else "400"
        fill = TEXT_HI if st.get("interchange") or st.get("terminal") else TEXT
        parts.append(
            f'<text x="{label_x:.1f}" y="{y + 4:.1f}" fill="{fill}" font-size="12" '
            f'font-family="{FONT}" font-weight="{weight}">{_esc(label)}</text>'
        )
    parts.append(
        f'<text x="{width / 2:.1f}" y="16" fill="{TEXT_DIM}" font-size="9" '
        f'font-family="{FONT}" text-anchor="middle">{count} stations · top to bottom</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def _linear_diagram(name: str, colour: str, stations: list[dict], *, show_all_labels: bool | None = None) -> str:
    if not stations:
        return ""
    count = len(stations)
    width = _view_width(count)
    height = 88 if count > 20 else 80
    y = 48.0
    x0, _ = _station_xy(0, count, y=y)
    x1, _ = _station_xy(count - 1, count, y=y)
    if show_all_labels is None:
        show_all_labels = count <= 14

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{_esc(name)} schematic">',
        f"<title>{_esc(name)}</title>",
        f'<rect width="{width}" height="{height}" fill="{BG}"/>',
        f'<line x1="{x0:.1f}" y1="{y:.1f}" x2="{x1:.1f}" y2="{y:.1f}" '
        f'stroke="{colour}" stroke-width="{LINE_W}" stroke-linecap="butt"/>',
    ]
    for i, st in enumerate(stations):
        x, cy = _station_xy(i, count, y=y)
        parts.append(_node_svg(x, cy, st, colour))
    for i, st in enumerate(stations):
        x, cy = _station_xy(i, count, y=y)
        lbl = _label_svg(x, cy + LABEL_Y_OFFSET, st, show_all=show_all_labels)
        if lbl:
            parts.append(lbl)
    parts.append(
        f'<text x="{width / 2:.1f}" y="14" fill="{TEXT_DIM}" font-size="8" '
        f'font-family="{FONT}" text-anchor="middle">{count} stations</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def _branch_diagram(name: str, spec: dict) -> str:
    colour = spec["colour"]
    branches = spec["branches"]
    junction_name = spec.get("junction", "Chan Sow Lin")
    ampang = branches["ampang"]
    sentul = branches["sentul"]
    south = branches["sri-petaling"]
    width, height = 640, 120
    jx, jy = 320.0, 72.0
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="{_esc(name)} schematic">',
        f"<title>{_esc(name)}</title>",
        f'<rect width="{width}" height="{height}" fill="{BG}"/>',
        f'<line x1="40" y1="{jy}" x2="{jx}" y2="{jy}" stroke="{colour}" stroke-width="{LINE_W}"/>',
        f'<line x1="{jx}" y1="{jy}" x2="{jx}" y2="28" stroke="{colour}" stroke-width="{LINE_W}"/>',
        f'<line x1="{jx}" y1="28" x2="520" y2="28" stroke="{colour}" stroke-width="{LINE_W}"/>',
        f'<line x1="{jx}" y1="{jy}" x2="600" y2="{jy}" stroke="{colour}" stroke-width="{LINE_W}"/>',
    ]
    for x, y, st in [(40, jy, sentul[0]), (520, 28, ampang[0]), (600, jy, south[-1])]:
        parts.append(_node_svg(x, y, st, colour))
        parts.append(_label_svg(x, y + (18 if y > 40 else -10), st, show_all=True))
    j_st = next((s for s in sentul if s["name"] == junction_name), {"interchange": True})
    parts.append(_node_svg(jx, jy, {**j_st, "interchange": True}, colour))
    parts.append(_label_svg(jx, jy + 18, {"abbr": "C.Sow Lin", "name": junction_name}, show_all=True))
    parts.append(
        f'<text x="{width / 2:.1f}" y="14" fill="{TEXT_DIM}" font-size="8" '
        f'font-family="{FONT}" text-anchor="middle">3 branches · Chan Sow Lin</text>'
    )
    parts.append("</svg>")
    return "\n".join(parts)


def _thumb_diagram(colour: str, _stations: list[dict]) -> str:
    """Minimal colour bar for line rows — no station dots (too small to read)."""
    width, height, y = 120, 8, 4.0
    x0, x1 = 4.0, float(width - 4)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" aria-hidden="true">'
        f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{colour}" stroke-width="6" stroke-linecap="round"/>'
        f"</svg>"
    )


def _kv_system_svg() -> str:
    w, h = 360, 160
    lines = [
        ("kelana-jaya", "#e31837", "M24,82 H336"),
        ("kajang", "#007a33", "M180,16 V144"),
        ("putrajaya", "#f4c300", "M260,24 L200,82 L120,140"),
        ("ampang-sri-petaling", "#f7941d", "M280,48 L200,82 L120,116"),
        ("monorail", "#8dc63f", "M168,70 L232,58"),
        ("lrt3", "#7b2d8e", "M60,40 V124"),
        ("ktm-komuter", "#0066b3", "M32,130 Q180,148 348,130"),
    ]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'role="img" aria-label="Klang Valley rail schematic">',
        f"<title>Klang Valley rail schematic</title>",
        f'<rect width="{w}" height="{h}" fill="{BG}"/>',
    ]
    for lid, colour, d in lines:
        parts.append(
            f'<path class="schem-line" data-line-id="{lid}" d="{d}" fill="none" '
            f'stroke="{colour}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>'
        )
    
    # Interchange rings
    ix = _load_marker("interchange-ring.svg")
    interchanges = [
        (180, 82),   # Pasar Seni (Kelana Jaya / Kajang)
        (200, 82),   # Tun Razak Exchange (Putrajaya / Ampang / Sri Petaling)
        (60, 82),    # Glenmarie (Kelana Jaya / LRT3)
        (180, 136),  # Kajang (Kajang / KTM Komuter)
    ]
    for x, y in interchanges:
        parts.append(_marker_at(ix, x, y, colour=TEXT_HI))

    # Line Labels
    line_labels = [
        ("kelana-jaya", "Kelana Jaya Line", "#e31837", 74, 76, "start"),
        ("lrt3", "Shah Alam Line (LRT3)", "#7b2d8e", 60, 32, "middle"),
        ("kajang", "Kajang Line", "#007a33", 180, 10, "middle"),
        ("putrajaya", "Putrajaya Line", "#f4c300", 270, 20, "start"),
        ("ampang-sri-petaling", "Ampang / Sri Petaling", "#f7941d", 288, 44, "start"),
        ("monorail", "KL Monorail", "#8dc63f", 236, 54, "start"),
        ("ktm-komuter", "KTM Komuter", "#0066b3", 32, 144, "start"),
    ]
    for lid, text, color, x, y, anchor in line_labels:
        parts.append(
            f'<text class="schem-text-label" data-line-id="{lid}" x="{x}" y="{y}" fill="{color}" '
            f'font-size="8" font-family="{FONT}" font-weight="700" text-anchor="{anchor}" '
            f'style="cursor:pointer">{text}</text>'
        )

    # Interchange Station Labels
    ix_labels = [
        ("Glenmarie", 60, 92, "middle"),
        ("Pasar Seni", 180, 92, "middle"),
        ("TRX", 212, 85, "start"),
        ("Kajang", 188, 139, "start"),
    ]
    for text, x, y, anchor in ix_labels:
        parts.append(
            f'<text x="{x}" y="{y}" fill="{TEXT_HI}" font-size="7" font-family="{FONT}" '
            f'font-weight="600" text-anchor="{anchor}">{text}</text>'
        )

    parts.append(
        f'<text x="8" y="{h - 6}" fill="{TEXT_DIM}" font-size="8" font-family="{FONT}">'
        f"Not geographic · open a line for station list</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts)


def _sync_stations_ordered(reference: dict, stations_data: dict) -> int:
    updated = 0
    ref_lines = {line["id"]: line for line in reference.get("lines", [])}
    for line_id, spec in stations_data.get("lines", {}).items():
        ref = ref_lines.get(line_id)
        if not ref:
            continue
        if spec.get("topology") == "branch":
            names: list[str] = []
            for branch in spec.get("branches", {}).values():
                for st in branch:
                    if st["name"] not in names:
                        names.append(st["name"])
        else:
            names = [st["name"] for st in spec.get("stations", [])]
        if names and ref.get("stations_ordered") != names:
            ref["stations_ordered"] = names
            updated += 1
    return updated


def _write_svg(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + "\n", encoding="utf-8")
    return str(path.relative_to(ROOT))


def build_all(*, sync_reference: bool = True) -> list[str]:
    stations_data = json.loads(STATIONS_PATH.read_text(encoding="utf-8"))
    reference = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    ref_by_id = {line["id"]: line for line in reference.get("lines", [])}
    written: list[str] = []

    for line_id, spec in stations_data.get("lines", {}).items():
        ref = ref_by_id.get(line_id, {})
        name = ref.get("name", line_id.replace("-", " ").title())
        colour = spec.get("colour") or ref.get("official_colour", "#64748b")
        if spec.get("topology") == "branch":
            svg = _branch_diagram(name, spec)
            thumb_stations = spec["branches"]["sentul"]
        elif spec.get("topology") == "complex":
            svg = _linear_diagram(name, colour, spec["stations"], show_all_labels=False)
            thumb_stations = spec["stations"]
        elif len(spec.get("stations", [])) > VERTICAL_THRESHOLD:
            svg = _vertical_diagram(name, colour, spec["stations"])
            thumb_stations = spec["stations"]
        else:
            svg = _linear_diagram(name, colour, spec["stations"])
            thumb_stations = spec["stations"]

        alias = LINE_ALIASES.get(line_id, line_id)
        targets = [
            LINES_DIR / f"{line_id}.svg",
            SCHEMATICS_DIR / f"{alias}.svg",
            LINES_DIR / f"{alias}.svg" if alias != line_id else None,
        ]
        for target in targets:
            if target:
                written.append(_write_svg(target, svg))

        thumb = _thumb_diagram(colour, thumb_stations)
        for target in [LINES_DIR / f"{line_id}-thumb.svg", SCHEMATICS_DIR / f"{alias}-thumb.svg"]:
            written.append(_write_svg(target, thumb))

    kv = _kv_system_svg()
    for target in [
        LINES_DIR / "kv-system.svg",
        SCHEMATICS_DIR / "kv-system-map.svg",
        DATA_DIR / "kv-system-map.svg",
    ]:
        written.append(_write_svg(target, kv))

    if sync_reference:
        if _sync_stations_ordered(reference, stations_data):
            REFERENCE_PATH.write_text(
                json.dumps(reference, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            written.append(str(REFERENCE_PATH.relative_to(ROOT)))

    return written


def main() -> int:
    written = build_all()
    for path in written:
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
