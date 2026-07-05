#!/usr/bin/env python3
"""Build Manus handoff zips — UI-only and full codebase (no secrets)."""
from __future__ import annotations

import shutil
import zipfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPORTS = REPO / "exports"
VAULT = Path(r"D:\MyVault\Projects")
TODAY = date.today().isoformat()

UI_PROMPT = """# Manus prompt — TrafficMY UI refinement

Copy everything below the line into Manus as your task prompt.

---

You are refining **TrafficMY**, a mobile-first Malaysia public transport pulse app.
Live reference: https://arifaqyl.me/traffic/

## Product (do not change the meaning)
- **Not** an official RapidKL/Prasarana site
- Answers: *"What are riders reporting on the network TODAY (MYT)?"*
- **Quiet ≠ all-clear** — never imply trains are fine when there are no reports
- Rider posts are synthesized professionally; never show raw usernames or full post text
- BM/EN bilingual toggle must stay

## What to refine (priority order)
1. **Line guide panel** — interchanges, route diagram, operating hours, route facts: clearer hierarchy, less confusion at dual-line stations (e.g. Bandar Utama, Glenmarie, KL Sentral)
2. **Map tab** — pins must sit on rail lines; line tap shows name + colour; float card must not overlap search bar
3. **Travel tab** — service hours card: commuter-useful (clickable rows, peak headway hints, timetable links)
4. **Live feed cards** — glance line (time · line · place · issue) scannable in 2 seconds
5. **Bottom nav + header** — active pill not clipped; travel banner text readable on gradient
6. **Visual polish** — keep Play/Stitch neubrutalist style (Nunito, green accent `#58CC02`, chunky cards, mascots on map pins)

## Tech constraints
- Vanilla HTML/CSS/JS only — **no React rewrite**
- Main files: `frontend/index.html`, `frontend/js/app.js`, `frontend/css/stitch.css`
- Deployed under subpath `/traffic/` — keep relative static paths (`static/...`, not absolute root)
- Map uses MapLibre + OpenFreeMap; rail geometry in `frontend/data/rail-lines.json`
- PWA service worker exists — bump cache version comment if you change static assets heavily

## Do NOT
- Remove trust/methodology disclaimers
- Add login, ads, or dark patterns
- Republish raw Threads/social text or @handles
- Claim live GPS train positions for LRT/MRT (rail RT feed is not stable)
- Break mobile 420px-first layout or 44px touch targets

## Deliverables
1. Updated `frontend/` files (HTML, CSS, JS) ready to drop into repo `static/`
2. Short changelog: what you changed and why (commuter benefit)
3. Screenshot descriptions for Home, Map, Line guide, Travel

## Reference docs in this zip
- `MANUS_README.md` — file map
- `UI_AUDIT.md` — known issues
- `PRODUCT.md` / `DESIGN.md` — product intent
"""

FULL_PROMPT = """# Manus prompt — TrafficMY full-stack context

Copy everything below the line into Manus if you need backend + frontend context.

---

You are helping improve **TrafficMY** (consumer) / **AduanMY** (engine) — Malaysia transport rider-signal intelligence.
Live: https://arifaqyl.me/traffic/ · Repo folder: `aduanmy/`

## Architecture
- **Collect:** Threads (primary), Reddit, RSS, official MyRapid/KTMB
- **Filter:** strict gates in `app/pipeline/extract.py` — today-MYT only, no noise
- **Publish:** professional summaries via `app/services/public_incident_service.py`
- **UI:** vanilla JS PWA in `static/`
- **Ops:** `scripts/threads_terminal.py` for collector health

## If refining UI
See UI zip prompt priorities: line guide, map pins on lines, travel schedule, trust copy.

## If refining backend/scraper
- Do not loosen `transport_rider_signal_worthwhile()` without labelled eval cases
- Threads session is in `data/private/` (not in this zip)
- GTFS is reference only — not incident truth

## Deliverables
State whether your changes are UI-only (`static/`) or backend (`app/`) and list files touched.
"""

UI_ZIP = EXPORTS / f"trafficmy-manus-ui-{TODAY}.zip"
FULL_ZIP = EXPORTS / f"trafficmy-manus-full-{TODAY}.zip"
VAULT_UI = VAULT / "trafficmy-manus-ui.zip"
VAULT_FULL = VAULT / "trafficmy-manus-full.zip"

SKIP_DIRS_ANYWHERE = {
    ".cursor",
    ".deepsec",
    ".git",
    ".playwright-cli",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "node_modules",
}
SKIP_DIRS_AT_ROOT = {"data", "output", "exports"}
SKIP_FILES = {".env", ".env.production", ".env.local", "threads-session.json"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".db", ".sqlite", ".sqlite3"}
SKIP_DIR_PREFIXES = (".pytest_", ".pytest-", ".tmp-pytest")


def should_skip(rel: Path) -> bool:
    if rel.parts and rel.parts[0] in SKIP_DIRS_AT_ROOT:
        return True
    if any(part in SKIP_DIRS_ANYWHERE or part.startswith(SKIP_DIR_PREFIXES) for part in rel.parts):
        return True
    if rel.name in SKIP_FILES or rel.suffix in SKIP_SUFFIXES:
        return True
    if "private" in rel.parts:
        return True
    return False


def write_zip(out: Path, files: list[tuple[Path, str]]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for src, arc in files:
            zf.write(src, arc.replace("\\", "/"))


def build_ui_zip() -> Path:
    pkg = EXPORTS / "manus-ui"
    if pkg.exists():
        shutil.rmtree(pkg)
    frontend = pkg / "frontend"
    shutil.copytree(REPO / "static", frontend)

    readme = pkg / "MANUS_README.md"
    readme.write_text(
        """# TrafficMY — Manus UI refinement pack

## Start here
1. Open **`MANUS_PROMPT.md`** — copy the prompt block into Manus
2. Upload this zip or point Manus at `frontend/`

## What this is
Live Play/Stitch UI for https://arifaqyl.me/traffic/ — mobile-first Malaysia transit pulse.

## Key files
- `frontend/index.html` — shell
- `frontend/js/app.js` — map, line guide, feed
- `frontend/css/stitch.css` — main theme
- `frontend/data/` — lines reference, rail geometry
""",
        encoding="utf-8",
    )
    (pkg / "MANUS_PROMPT.md").write_text(UI_PROMPT, encoding="utf-8")

    for name in ("PRODUCT.md", "DESIGN.md", "README.md"):
        src = REPO / name
        if src.is_file():
            shutil.copy2(src, pkg / name)

    docs = REPO / "docs" / "UI_AUDIT.md"
    if docs.is_file():
        shutil.copy2(docs, pkg / "UI_AUDIT.md")

    files: list[tuple[Path, str]] = []
    for path in sorted(pkg.rglob("*")):
        if path.is_file():
            files.append((path, path.relative_to(pkg.parent).as_posix()))
    write_zip(UI_ZIP, files)
    shutil.copy2(UI_ZIP, VAULT_UI)
    return UI_ZIP


def build_full_zip() -> Path:
    files: list[tuple[Path, str]] = []
    for path in sorted(REPO.rglob("*")):
        rel = path.relative_to(REPO)
        if should_skip(rel):
            continue
        if path.is_file():
            files.append((path, f"aduanmy/{rel.as_posix()}"))

    manifest = EXPORTS / "MANUS_FULL_README.md"
    manifest.write_text(
        """# TrafficMY / AduanMY — full codebase handoff (no secrets)

## Start here
1. **`MANUS_PROMPT.md`** — copy-paste prompt for Manus
2. `README.md`, `ROADMAP.md`, `docs/HANDOFF_FOR_REVIEW.md`

## Stack
Python FastAPI + vanilla JS PWA. Live at https://arifaqyl.me/traffic/

## Excluded
- `data/` runtime DB, `data/private/` Threads session, `.env*`
""",
        encoding="utf-8",
    )
    prompt_path = EXPORTS / "MANUS_FULL_PROMPT.md"
    prompt_path.write_text(FULL_PROMPT, encoding="utf-8")
    files.append((manifest, "aduanmy/MANUS_README.md"))
    files.append((prompt_path, "aduanmy/MANUS_PROMPT.md"))
    write_zip(FULL_ZIP, files)
    shutil.copy2(FULL_ZIP, VAULT_FULL)
    return FULL_ZIP


def main() -> None:
    ui = build_ui_zip()
    full = build_full_zip()
    print(f"UI zip:   {ui}  ({ui.stat().st_size / (1024 * 1024):.2f} MB)")
    print(f"         {VAULT_UI}")
    print(f"Full zip: {full}  ({full.stat().st_size / (1024 * 1024):.2f} MB)")
    print(f"         {VAULT_FULL}")


if __name__ == "__main__":
    main()
