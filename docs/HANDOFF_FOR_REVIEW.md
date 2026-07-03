# TrafficMY — Handoff for Review

**Last updated:** 2026-06-28  
**Repo:** `D:\aduanmy\`  
**Live:** https://arifaqyl.me/traffic/  
**Health:** https://arifaqyl.me/traffic/api/health  

Use this document to onboard another AI or developer. Everything below is based on the actual repo state at handoff time — not aspirational.

---

## 1. Project overview

**TrafficMY** is a Malaysia-first public transport status board. It surfaces **crowd-reported delays** from Threads and other public posts, with optional official corroboration and GTFS bus GPS. It is **not** an official RapidKL/KTMB status product.

| Item | Detail |
|------|--------|
| Product wedge | Transport on shared AduanMY ingest pipeline |
| Live URL | https://arifaqyl.me/traffic/ |
| API base | `/traffic/api/` (nginx subpath; frontend uses `APP_BASE` detection) |
| Deploy | `python D:\aduanmy\scripts\deploy_do.py` (paramiko SSH to DigitalOcean — **not** PowerShell SSH) |
| Remote path | `/root/trafficmy` on droplet `68.183.181.237` |
| Stack | Python 3.12, FastAPI, SQLite, single-file `static/index.html`, Leaflet (lazy-loaded), Docker |
| Typography | IBM Plex Sans + Mono, Barlow Condensed (brand), warm stone palette per `docs/TASTE.md` |
| Scope | Malaysia transport only, English UI |

---

## 2. Architecture

### Backend (`app/`)

```
Browser → nginx /traffic/ → FastAPI :8000 (Docker :8002)
                              ├── SQLite /data/aduanmy.db
                              └── static/index.html + static/*
```

| Layer | Path | Role |
|-------|------|------|
| API routes | `app/api/routes/` | `incidents.py`, `journey.py`, `health.py`, `trends.py`, `scoring.py` |
| Collectors | `app/collectors/` | `threads/`, `reddit/`, `x/`, `official/`, `rss/`, `gtfs/` |
| Pipeline | `app/pipeline/` | `extract.py`, `bus_alerts.py`, `geo.py` |
| Services | `app/services/` | `ingest_service`, `line_status_service`, `map_service`, `journey_service`, etc. |
| Config | `configs/` | `discovery.yaml`, `gtfs.yaml`, `entities.yaml`, `locations.yaml` |
| Scheduler | `app/services/scheduler_service.py` | GTFS every 5m, full ingest every 30m |

### Data flow (Threads-first)

```
Threads keyword search (Playwright) ──┐
Reddit / RSS / Official / X ──────────┼→ ingest_service.run_ingest()
GTFS anomalies (bus GPS) ─────────────┘         │
                                                ▼
                              transform_rows → cluster_id → SQLite complaints
                                                │
                                                ▼
                    line_status_service.get_line_status_board()  (social default)
                                                │
                                                ▼
                              GET /api/trafficmy/lines → static/index.html
```

**GTFS role (secondary):**
- Static GTFS → station graph for journey planner + map station coords
- GTFS-RT → optional bus vehicle positions on map (`vehicles=false` default)
- GTFS anomaly rows exist in DB but UI defaults to `source_group=social`

### Frontend

- **Monolith:** `static/index.html` (~4k lines) — HTML + CSS + vanilla JS
- Tabs: Status | Map | Plan | Passes
- Mobile: bottom nav, bottom-sheet line guide, FAB refresh, header search bar
- Desktop: right panel (400px) for line guide / incident drawer

---

## 3. Everything implemented (honest status)

### UX research applied
| Item | Status | Notes |
|------|--------|-------|
| TfL / SuperNYC / JR / MyRapid patterns | DONE | Documented in `docs/PRODUCT_RESEARCH.md`, `docs/IDEAS_STOLEN.md` |
| Anti-slop (`docs/TASTE.md`) | PARTIAL | IBM Plex, stone palette, no Inter — but user still complained about earlier cyan/gradient phase |
| Threads-first copy | DONE | Intro, map disclaimers, community reports |

### Core product
| Feature | Status | Notes |
|---------|--------|-------|
| Line status board | DONE | `GET /api/trafficmy/lines`, severity badges with text |
| Line guide drawer | DONE | Interchanges → schematic → Threads riders → hours |
| Incident evidence drawer | DONE | `GET /api/trafficmy/incidents/{cluster_id}` |
| Interchanges API | DONE | Walking notes, transfer steps |
| Honest empty status | DONE | `No recent reports`; never infers normal service from silence |
| Community reports (single feed) | DONE | **Fixed 2026-06-28** — removed duplicate "What riders report" vs "Recent reports" |
| Official corroboration strip | DONE | Separate from community feed |
| Journey planner | DONE | GTFS graph, `/api/trafficmy/journey/plan` |
| Pass comparison | DONE | Rapid KL estimate |

### Map
| Feature | Status | Notes |
|---------|--------|-------|
| `/api/trafficmy/map/live` | DONE | Threads-first report pins |
| Rail geometry layer | DONE | `static/data/rail-lines.json` |
| Bus GPS layer | DONE | Default **OFF**, label "Official GPS (may lag)" |
| Lazy Leaflet load | DONE | Only when Map tab opened |
| Tablet split (list + map) | PARTIAL | CSS grid exists; sidebar is compact line list |

### Schematics
| Feature | Status | Notes |
|---------|--------|-------|
| `scripts/build_line_svgs.py` | DONE | Composes from `static/assets/markers/` |
| `static/data/line-stations.json` | DONE | Station order for KV lines |
| Output SVGs | DONE | `static/lines/*.svg`, thumbs, `kv-system.svg` |
| User satisfaction | **OPEN** | User said "schematics all bad" — programmatic linear style may need label density / interchange polish |
| Interactive station taps | NOT STARTED | Line guide shows static `<img>` only |

### Phase 1 features (from roadmap)
| Feature | Status | Notes |
|---------|--------|-------|
| Smart search (`/`, Cmd+K) | PARTIAL | Station API search + `placeFilter`; no unified line+station result picker |
| Favorites / My lines | DONE | `localStorage`, Pin button, filter chip |
| Mobile bottom sheet | PARTIAL | CSS bottom sheet + drag handle; needs UX QA |
| Desktop right panel | DONE | 400px overlay |
| Bottom nav | DONE | Status / Map / Plan / Passes |
| 48px tap targets | PARTIAL | Chips/rows updated; not fully audited |
| Reliability badges | NOT STARTED | `health_score` exists; no "Usually quiet" / "Often reported" labels |
| Nearby Me | NOT STARTED | No API, no header button |
| Get Me Home | NOT STARTED | No geolocation heuristic button |
| Rider pulse filter chips | NOT STARTED | No All/Delays/Crowded filters on community feed |
| Report on Threads CTA | PARTIAL | Text CTA only; no pre-filled search URL button |
| Data freshness everywhere | PARTIAL | Header `liveMeta`, `relTime()` on reports; not on every card |
| deepsec security scan | PARTIAL | `.deepsec/` folder created via `npx deepsec init`; **no AI process run** (no API keys); scan export not verified |

### OSS documentation
| Doc | Status |
|-----|--------|
| `docs/OPEN_SOURCE_STACK.md` | DONE (partial repo list — see §9 for expansion targets) |
| `static/assets/README.md` | DONE |
| `docs/ARCHITECTURE.md` | DONE |
| `docs/TASTE.md` | DONE |
| `docs/METRO_SCHEMATIC_RESEARCH.md` | NOT STARTED |

---

## 4. API endpoints

Base: `/traffic/api` in production. Paths below are router paths (prepend `/api`).

### Health & refresh
| Method | Path | Params | Notes |
|--------|------|--------|-------|
| GET | `/health` | — | `threads_count`, `primary_signal`, ingest age |
| POST | `/refresh` | Header `X-Dashboard-Refresh: 1` or `X-API-Key` | Triggers full ingest |

### TrafficMY core
| Method | Path | Key params |
|--------|------|------------|
| GET | `/trafficmy/status` | — |
| GET | `/trafficmy/config` | — |
| GET | `/trafficmy/methodology` | — |
| GET | `/trafficmy/overview` | `include_stale`, `source_group`, `quality_only`, `malaysia_only` |
| GET | `/trafficmy/lines` | `source_group` (default `social`), `quality_only` (default `true`), `malaysia_only` |
| GET | `/trafficmy/lines/reference` | — |
| GET | `/trafficmy/lines/{line_id}/info` | — |
| GET | `/trafficmy/interchanges` | — |
| GET | `/trafficmy/incidents` | `sort_by`, `confidence_band`, `severity`, `entity`, `location`, `state`, `mode`, `source_group`, `freshness_band`, `quality_only`, `include_stale`, `malaysia_only` |
| GET | `/trafficmy/incidents/{cluster_id}` | — |

### Map & journey
| Method | Path | Key params |
|--------|------|------------|
| GET | `/trafficmy/map/live` | `vehicles` (default `false`), `vehicle_limit`, `report_limit` |
| GET | `/trafficmy/map/stations` | `limit`, `layer` (`rail` \| `bus`) |
| GET | `/trafficmy/map/rail-lines` | — |
| GET | `/trafficmy/map/station` | `name` |
| GET | `/trafficmy/stations` | `q`, `limit` (locations.yaml) |
| GET | `/trafficmy/journey/stations` | `q`, `limit` (GTFS) |
| GET | `/trafficmy/journey/plan` | `origin`, `destination` |

### Other
| Method | Path | Notes |
|--------|------|-------|
| GET | `/trafficmy/updates` | Offers & launches |
| GET | `/trafficmy/pass-comparison` | `rides_per_month`, `average_fare`, `malaysian`, `student` |
| GET | `/complaints`, `/clusters`, `/clusters/{id}` | Legacy AduanMY |
| GET | `/trends`, `/scores` | Legacy |

---

## 5. Key files to read first

| File | Purpose |
|------|---------|
| `static/index.html` | Entire UI — board, map, tabs, drawers, search |
| `app/services/line_status_service.py` | Line board + `recent_reports` |
| `app/services/map_service.py` | Live map pins, station markers |
| `app/services/ingest_service.py` | Full + GTFS ingest orchestration |
| `app/collectors/threads/client.py` | Primary Threads keyword search |
| `app/pipeline/extract.py` | Complaint filtering, noise rejection |
| `app/services/overview_service.py` | Social vs GPS filtering, confidence |
| `static/data/lines-reference.json` | Line metadata, interchanges, hours |
| `static/data/line-stations.json` | Schematic station order |
| `scripts/build_line_svgs.py` | Generate line SVGs |
| `scripts/deploy_do.py` | Production deploy |
| `configs/discovery.yaml` | Threads search keywords |
| `docs/TASTE.md` | Anti-slop design rules |
| `docs/OPEN_SOURCE_STACK.md` | OSS references |
| `docs/ARCHITECTURE.md` | System diagram |
| `tests/test_routes.py` | API contract tests |

---

## 6. Known bugs & usability issues

### From user / transcript complaints
- **"Schematics all bad"** — linear SVGs exist but dense lines (Kelana 37 stations) may be unreadable; user wanted TfL/MTR-quality diagrams
- **"Ugly" UI** — earlier cyan gradient phase; partially reverted to TASTE palette; may still need polish
- **Duplicate feeds** — **FIXED**: single **Community reports**
- **Filter chips stuck empty** — **FIXED** (2026-06-28): `boardSnapshot`, chip counts, All resets search
- **Map blue KTM loop** — **FIXED**: rebuilt from GTFS shapes; KTM omitted until real data
- **Loading stuck** — past JS syntax bug in `fetch(api(...)` — fixed; watch for regressions
- **GTFS drowning Threads** — fixed via default `source_group=social` on board
- **Timezone "8h ago" bug** — fixed (UTC ISO in API)
- **Empty board with `quality_only=true`** — aggressive filters + quiet periods → looks broken; consider UI copy or looser default for demo
- **Slow scrape** — full ingest ~2–3 min; Threads lane ~160s (see health `timings.threads`)
- **Mobile UX** — bottom sheet partially implemented; needs real-device QA at 375px

### From pytest (2026-06-28)
```
194 passed, 0 failed, 1 deprecation warning
```

The map route test double now accepts `layer`; Threads tests cover the intended native-search → watchlist → external fallback order and skip watchlist after six native results.

### Code smells to check
- `static/index.html` is 4k+ lines — hard to maintain
- Many `scripts/probe_*.py` — dev-only, not tests

---

## 7. Product decisions

| Decision | Choice |
|----------|--------|
| Primary signal | **Threads** keyword search |
| Official status | Not claimed; crowd reports with disclaimers |
| GTFS bus GPS | Optional, off by default, "may lag" |
| No rail train GPS | Never fake positions |
| Geography | Malaysia only |
| Language | English UI |
| Status window | 24h for line severity; older reports remain evidence only |
| Live window | 21 days for report listing |
| Default board filter | `source_group=social`, `quality_only=true` |
| Design | Anti-slop per TASTE.md — no gradients, no Inter, functional route colours |
| Schematics | Original MY geometry; OSS marker components; no copyrighted map hotlinking |
| Deploy | `deploy_do.py` only; secrets in `D:\MyVault\SECRETS.md` — **never expose** |

---

## 8. What NOT to do

- **Do not commit** unless user explicitly asks
- **Do not expose** contents of `D:\MyVault\SECRETS.md` or `.env`
- **Do not use** PowerShell SSH to droplet — use `python scripts/deploy_do.py`
- **Do not** run `deepsec process` without user approval (costs $$$)
- **Do not** add Tailwind or heavy JS frameworks without discussion
- **Do not** hotlink TfL/MTR/MyRapid copyrighted map artwork
- **Do not** present crowd "Normal" as official all-clear

---

## 9. Suggested priorities for next reviewer

### P0 — Bugs
No known test or launch blocker as of the current review.

### P1 — Usability
1. QA the mobile bottom sheet and map interactions at 375px on a real device
2. Complete Phase 1 partials: Nearby Me, reliability badges, pulse filter chips, Threads report button
3. Smart search: filter line board by name + station in one UI
4. Data freshness label in header: "Rider reports · updated X min ago"
5. Schematic readability pass (Kelana density, interchange rings)

### P2 — Features (from OSS research — expand `OPEN_SOURCE_STACK.md`)
- Catenary Maps / Instabus / morganney/busmap patterns for map UX
- vasile/transit-map vehicle animation along polylines
- conveyal/transitive.js route layers
- Interactive schematic station list in line guide

### P3 — Data
- Threads ingest speed / keyword tuning in `configs/discovery.yaml`
- `quality_only=false` toggle or better empty-state copy when board is quiet

---

## 10. Git & test status (2026-06-28)

### Git
- **Branch:** working tree on `aduanmy` (mostly uncommitted migration)
- **Modified tracked files:** 35 (`git diff --stat`: ~6443 insertions, ~1364 deletions in tracked files)
- **Untracked:** majority of TrafficMY app (`app/services/*`, `static/lines/*`, `docs/*`, `scripts/*`, `.deepsec/`, etc.)
- **Commit policy:** user has not requested commits — treat as dirty working tree

### Tests
```bash
cd D:\aduanmy
python -m pytest --basetemp=D:\aduanmy\.pytest_tmp -q
# Result: 194 passed, 0 failed, 1 deprecation warning
```

### Live site (verified 2026-06-28)
```json
{
  "status": "ok",
  "threads_count": 11,
  "primary_signal": "threads",
  "ingest_age_minutes": 17.8,
  "is_stale": false
}
```
- UI shows **Community reports** (duplicate feed removed)
- URL: https://arifaqyl.me/traffic/

### deepsec
- `.deepsec/` directory exists (from `npx deepsec init`)
- No `AI_GATEWAY_API_KEY` or `ANTHROPIC_AUTH_TOKEN` in environment or vault grep
- AI `process` stage was **not run** — no findings export
- To run free regex scan: `cd D:\aduanmy\.deepsec && pnpm install && pnpm deepsec scan`

---

## Quick start for reviewer

```bash
cd D:\aduanmy
pip install -e .
python -m pytest --basetemp=D:\aduanmy\.pytest_tmp -q
uvicorn app.main:app --reload --port 8000
# Open http://127.0.0.1:8000/

python scripts/build_line_svgs.py   # regenerate schematics
python scripts/deploy_do.py         # deploy (needs vault password)
```

Also read: `docs/AI_REVIEW_PROMPTS.md` for copy-paste prompts per task type.
