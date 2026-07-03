# TrafficMY — AI Review Prompts

Copy-paste any block below into a new AI chat. Each prompt is self-contained but points to `docs/HANDOFF_FOR_REVIEW.md` for full context.

**Repo:** `D:\aduanmy\`  
**Live:** https://arifaqyl.me/traffic/  
**Constraints:** No git commit unless user asks. Deploy via `python D:\aduanmy\scripts\deploy_do.py`. Secrets in `D:\MyVault\SECRETS.md` — read if needed, never expose values.

**Engineering workflow:** Reproduce first, trace root cause, make a surgical change, run focused + full tests, then independently verify runtime behavior. Adapted from [engineering-discipline](https://github.com/tmdgusya/engineering-discipline).

---

## Prompt A — Full audit & bug hunt

```
You are reviewing TrafficMY, a Malaysia-first public transport status board.

Repo: D:\aduanmy\
Live: https://arifaqyl.me/traffic/
Handoff doc: D:\aduanmy\docs\HANDOFF_FOR_REVIEW.md (read this first)

Stack: Python FastAPI + SQLite backend, single-file frontend static/index.html, deployed to DigitalOcean via scripts/deploy_do.py.

Your task:
1. Read HANDOFF_FOR_REVIEW.md and skim static/index.html, app/services/line_status_service.py, app/collectors/threads/client.py
2. Run: cd D:\aduanmy && python -m pytest --basetemp=D:\aduanmy\.pytest_tmp -q
3. Hunt for bugs: broken API paths, JS errors, panel/focus issues, timezone/freshness, empty board with quality_only, test failures
4. Check live: https://arifaqyl.me/traffic/api/health

Return a prioritized bug list:
- P0 (broken for users)
- P1 (wrong/confusing)
- P2 (nice to fix)

Each item must include: symptom, likely root cause, file path(s), suggested minimal fix.

Rules:
- Do NOT commit unless I ask
- Do NOT expose secrets from D:\MyVault\SECRETS.md
- Minimal focused diffs only
- Deploy after fixes: python D:\aduanmy\scripts\deploy_do.py
```

---

## Prompt B — Usability / mobile UX pass

```
TrafficMY mobile + desktop UX review.

Repo: D:\aduanmy\
Live: https://arifaqyl.me/traffic/
Read: D:\aduanmy\docs\HANDOFF_FOR_REVIEW.md, D:\aduanmy\docs\TASTE.md
Main UI: D:\aduanmy\static\index.html

Focus areas:
- Mobile (<768px): bottom nav, bottom-sheet line guide (drag handle), FAB refresh, 48px tap targets, full-viewport map
- Desktop (>1024px): 400px right panel for line guide, max-width layout
- Loading states: board skeleton, stale banner, refresh feedback
- Header: liveMeta freshness, search prominence
- Panel: showPanel() focus trap, Escape to close

Test mentally at 375px, 768px, 1280px. Fix obvious issues with minimal CSS/JS diffs.

Anti-slop: IBM Plex, warm stone palette (#111318, #ece8e1, #c2410c accent), no gradients/glows per TASTE.md.

Threads-first: crowd reports prominent; bus GPS optional and off by default.

Rules:
- No Tailwind (use existing CSS in index.html)
- No commit unless asked
- Deploy: python D:\aduanmy\scripts\deploy_do.py
```

---

## Prompt C — Feature completion (Phase 1 partials)

```
Complete Phase 1 partial features for TrafficMY.

Repo: D:\aduanmy\
Handoff: D:\aduanmy\docs\HANDOFF_FOR_REVIEW.md (see §3 feature status table)

Implement what's missing or partial:

1. Nearby Me — header "Nearby" button, geolocation, closest stations from GTFS graph or /api/trafficmy/map/stations, list with distance km, tap → map pan
2. Smart search — always visible, debounced, filter line board + stations, / and Cmd+K focus
3. Reliability badges per line — "Some reports" | "Often reported" | "Unreliable today" from the 24h report count; never infer "quiet" or normal service from missing reports
4. Get Me Home — geolocation + time-of-day heuristic toward KV hubs (KL Sentral, etc.)
5. Rider pulse filter chips on community feed: All | Delays | Crowded | Today
6. Report on Threads — button with search URL template (#rapidkl @askrapidkl)
7. Interactive schematic — station list below line guide schematic, tap → highlight

Mark each DONE in HANDOFF when complete. Add API endpoint + test if you add /api/trafficmy/nearby.

Rules: Threads-first, English UI, Malaysia only, no commit unless asked, deploy via deploy_do.py, no secrets in output.
```

---

## Prompt D — Visual / anti-slop design pass

```
TrafficMY visual design pass — anti-slop compliance.

Repo: D:\aduanmy\
Read: D:\aduanmy\docs\TASTE.md (authoritative), D:\aduanmy\docs\HANDOFF_FOR_REVIEW.md
UI: D:\aduanmy\static\index.html
Schematics: D:\aduanmy\static\lines\*.svg, D:\aduanmy\scripts\build_line_svgs.py

User previously said schematics are "all bad" and UI was "ugly". Fix with taste, not decoration.

Tasks:
1. Audit index.html against TASTE.md REJECT/REQUIRE lists
2. Polish line schematics: readability on Kelana (37 stations), interchange rings, terminal squares — edit build_line_svgs.py + markers in static/assets/markers/
3. Ensure route colours are functional only (not page chrome)
4. Severity = colour AND text label on every badge
5. No cyan gradients, no Inter, no purple glows, no emoji empty states

Run: python D:\aduanmy\scripts\build_line_svgs.py after schematic changes.

Rules: OSS SVG components only (documented in static/assets/README.md). No AI-generated map art. No commit unless asked. Deploy after meaningful visual changes.
```

---

## Prompt E — Data & scraping (Threads-first)

```
TrafficMY data pipeline review — Threads-first, honest freshness.

Repo: D:\aduanmy\
Read: D:\aduanmy\docs\HANDOFF_FOR_REVIEW.md, D:\aduanmy\docs\ARCHITECTURE.md
Key files:
- app/collectors/threads/client.py
- app/services/ingest_service.py
- app/pipeline/extract.py
- configs/discovery.yaml
- app/services/line_status_service.py (quality_only, 24h status window)

Investigate:
1. Why board can look empty with quality_only=true + quiet periods
2. Threads ingest speed (health timings.threads ~160s) — can we improve?
3. Noise in extract.py — false positives vs missed real complaints
4. GTFS must stay secondary (source_group=social default on board)
5. Freshness: header should say "Rider reports · updated X min ago"

Probe live: curl https://arifaqyl.me/traffic/api/health
Run ingest locally if safe. Fix filters/copy, not architecture rewrites.

Rules: No commit unless asked. Run pytest after changes. Deploy via deploy_do.py.
```

---

## Prompt F — Security review (manual, no deepsec cost)

```
Security review for TrafficMY — manual + pytest, NO paid deepsec AI process.

Repo: D:\aduanmy\
Read: D:\aduanmy\SECURITY.md, D:\aduanmy\docs\HANDOFF_FOR_REVIEW.md

Check:
1. POST /api/refresh auth — app/api/routes/incidents.py _refresh_allowed()
2. XSS in static/index.html — esc() usage on user-derived text
3. No secrets in repo (.env, probe files, scripts)
4. Scraper input handling in collectors
5. CORS / host validation on refresh endpoint
6. SQLite injection (should be parameterized)

Run: python -m pytest --basetemp=D:\aduanmy\.pytest_tmp -q

Optional free scan only:
  cd D:\aduanmy\.deepsec && pnpm deepsec scan
(Do NOT run deepsec process without user API key approval — costs money)

Fix CRITICAL/HIGH issues with minimal diffs. Add note to SECURITY.md if you document scan workflow.

Rules: Never expose D:\MyVault\SECRETS.md values. No commit unless asked.
```

---

## Prompt G — Master prompt (full context for new chat)

```
# TrafficMY — Master review & build prompt

You are working on TrafficMY at D:\aduanmy\ — a Malaysia-first public transport status board. Read D:\aduanmy\docs\HANDOFF_FOR_REVIEW.md first for full current state.

## What it is
- Crowd-reported rail/bus delays from Threads (primary), Reddit, RSS, official notices
- NOT official RapidKL/KTMB status — honest disclaimers everywhere
- Live: https://arifaqyl.me/traffic/
- API health: https://arifaqyl.me/traffic/api/health

## Stack
- Backend: Python 3.12, FastAPI, SQLite (complaints table), Docker on DigitalOcean
- Frontend: static/index.html monolith (~4k lines), Leaflet lazy-loaded on Map tab
- Deploy: python D:\aduanmy\scripts\deploy_do.py (paramiko — NOT PowerShell SSH)
- Secrets: D:\MyVault\SECRETS.md (NEVER expose values in your output)

## Architecture (Threads-first)
Threads keyword search → ingest_service → SQLite clusters → line_status_service → GET /api/trafficmy/lines → UI board
GTFS: static for journey planner; GTFS-RT bus GPS optional on map (default OFF, "may lag")

## Key files
- static/index.html — entire UI
- app/services/line_status_service.py — line board + recent_reports
- app/services/map_service.py — /api/trafficmy/map/live
- app/collectors/threads/client.py — primary scraper
- scripts/build_line_svgs.py — line SVG schematics
- docs/TASTE.md — anti-slop design rules (IBM Plex, stone palette, no gradients)

## What's DONE (recent)
- Line status board, line guide drawer, station list in guide, fullscreen schematic modal
- Map: GTFS rail shapes (LRT/MRT/Monorail toggles), interchange markers with "change to" lines, removed fake KTM blue loop
- Filter chips with counts: All (17) / My lines / Rail / Bus — boardSnapshot fix (filters no longer stick empty)
- Favorites (localStorage + Pin), mobile bottom nav, community reports single feed
- 194 tests passing

## Known user pain (prioritize)
- Schematics still need polish (dense lines, expand UX)
- UI feels "not very usable" — user wants professional transit app (TfL / Citymapper tier), not generic
- Empty board when quiet (quality_only) can look broken
- static/index.html is 4k+ lines — consider surgical refactors only

## What's PARTIAL / NOT STARTED
- Nearby Me, Get Me Home, reliability badges, pulse filter chips
- Interactive schematic station taps
- Smart search (unified line + station)
- Schematic polish (user said "all bad" on dense lines)
- Current suite is green; reproduce any new failure before editing

## Product rules
- Threads-first truth layer, English UI, Malaysia only
- No Tailwind, no AI slop visuals, no copyrighted map hotlinking
- No git commit unless I explicitly ask
- Never label missing crowd reports as official normal or all-clear service
- Run tests: python -m pytest --basetemp=D:\aduanmy\.pytest_tmp -q
- Deploy after meaningful changes: python D:\aduanmy\scripts\deploy_do.py

## Your task
[DESCRIBE YOUR TASK HERE — e.g. "fix all failing tests and complete Nearby Me"]

Start by reading HANDOFF_FOR_REVIEW.md, then inspect the relevant files. Make minimal focused changes. Report what you changed and verify live if you deploy.
```

---

## Quick reference

| Prompt | Use when |
|--------|----------|
| A | First pass on repo — find bugs |
| B | Mobile/desktop UX |
| C | Ship Phase 1 features |
| D | Visual + schematics polish |
| E | Scraping, empty board, freshness |
| F | Security without AI scan cost |
| G | New chat with full context |
| H | **Bugs + UI redesign** (use this now) |

---

## Prompt H — Bugs + UI redesign (recommended now)

```
# TrafficMY — Bug hunt + UI improvement pass

You are a senior product engineer reviewing TrafficMY before the next release.

## Read first (in order)
1. D:\aduanmy\docs\HANDOFF_FOR_REVIEW.md
2. D:\aduanmy\docs\TASTE.md (anti-slop design — MUST follow)
3. D:\aduanmy\docs\PRODUCT_RESEARCH.md (TfL, SuperNYC, JR patterns)
4. D:\aduanmy\static\index.html (entire UI — ~4k lines)

## Project
- Malaysia transit status board — Threads-first crowd delays, NOT official RapidKL
- Live: https://arifaqyl.me/traffic/
- Repo: D:\aduanmy\
- Deploy: python D:\aduanmy\scripts\deploy_do.py
- Tests: python -m pytest --basetemp=D:\aduanmy\.pytest_tmp -q (194 should pass)
- Secrets: D:\MyVault\SECRETS.md — never expose values
- Do NOT git commit unless I explicitly ask

## Recently fixed (don't re-break)
- Line board filters: boardSnapshot + chip counts (All/Rail/Bus/My lines); All clears search
- Map: GTFS shapes, LRT/MRT/Monorail toggles, interchange popups with transfer lines
- Single community reports feed; honest "no recent reports"
- Line guide: scrollable station list + optional route diagram

## Phase 1 — Bug hunt
1. Run pytest
2. Test live at 375px and 1280px: filter chips, Pin/My lines, line guide, map, search clear
3. List P0/P1/P2 bugs with file paths

## Phase 2 — UI improvements
Follow TASTE.md: IBM Plex, stone palette, burnt-orange accent — no gradients/glows/Inter.
Reference TfL/Citymapper/JR clarity. Improve: line board, mobile header, bottom sheet, map, schematics, empty states.

## Output
Bug list, UI changes, files touched, test results, deploy + live check.
```
