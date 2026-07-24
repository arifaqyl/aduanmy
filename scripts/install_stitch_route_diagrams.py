"""Install Stitch route-diagram PNGs and point lines-reference at them."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / ".stitch-incoming" / "route_diagrams_pack" / "stitch_task_execution_engine"
LINES_DIR = REPO / "static" / "lines"
REF_PATH = REPO / "static" / "data" / "lines-reference.json"

# folder name fragment -> (dest filename, line id to update in reference)
MAPPING = [
    ("ampang_sri_petaling_lrt", "ampang-sri-petaling.png", "ampang-sri-petaling"),
    ("kajang_mrt_line", "kajang.png", "kajang"),
    ("kelana_jaya_lrt_line", "kelana-jaya.png", "kelana-jaya"),
    ("kl_monorail_line", "monorail.png", "monorail"),
    ("lrt3_shah_alam_line", "lrt3.png", "lrt3"),
    ("putrajaya_mrt_line", "putrajaya.png", "putrajaya"),
    ("ktm_komuter_klang", "ktm-komuter.png", "ktm-komuter"),
    ("ktm_komuter_utara", "ktm-komuter-utara.png", None),
    ("ktm_ets_intercity", "ktm-ets.png", None),
    ("klia_ekspres_klia", "klia-ekspres.png", None),
    ("brt_sunway_line", "brt-sunway.png", None),
    ("sabah_state_railway", "sabah-railway.png", None),
    ("malaysian_bus_networks", "bus-networks.png", None),
    ("bas.my_network", "bas-my-network.png", None),
]


def find_screen(fragment: str) -> Path | None:
    for folder in SRC.iterdir():
        if not folder.is_dir():
            continue
        if fragment in folder.name:
            screen = folder / "screen.png"
            if screen.exists():
                return screen
    return None


def main() -> None:
    LINES_DIR.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for fragment, dest_name, line_id in MAPPING:
        src = find_screen(fragment)
        if not src:
            print("MISSING", fragment)
            continue
        dest = LINES_DIR / dest_name
        shutil.copy2(src, dest)
        rel = f"lines/{dest_name}"
        copied[dest_name] = rel
        print(f"copied {dest_name} ({dest.stat().st_size} bytes) <- {src.parent.name}")
        if line_id:
            copied[f"id:{line_id}"] = rel

    data = json.loads(REF_PATH.read_text(encoding="utf-8"))
    updated = 0
    for line in data.get("lines", []):
        lid = line.get("id")
        key = f"id:{lid}"
        if key in copied:
            old = line.get("schematic_svg")
            line["schematic_svg"] = copied[key]
            # keep svg as fallback field for tools that expect svg
            if old and old.endswith(".svg"):
                line["schematic_svg_fallback"] = old
            updated += 1
            print(f"ref {lid}: {old} -> {copied[key]}")
    REF_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated {updated} line references")


if __name__ == "__main__":
    main()
