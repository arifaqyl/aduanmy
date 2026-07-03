# TrafficMY / AduanMY Architecture

Malaysia-first public complaint intelligence. **TrafficMY** is the transport wedge product built on the shared AduanMY ingest pipeline.

## System overview

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser  →  nginx /traffic/  →  FastAPI :8000 (Docker :8002)   │
│              static/index.html     SQLite /data/aduanmy.db        │
└─────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
   Scheduler thread     operator refresh     GET /api/trafficmy/*
   (full 15m + backup 6h)
         │
         ▼
   ingest_service.run_ingest()
         │
         ├─ ThreadPoolExecutor (6 collectors in parallel)
         │     threads ──► authenticated web search → public search → watchlist → seeds
         │     reddit  ──► old.reddit HTML search + seeds
         │     x       ──► paused until authenticated
         │     official► MyRapid / KTMB / telco outage pages
         │     rss     ──► Google News RSS feeds
         │     gtfs    ──► reference-only; anomaly inference disabled
         │
         ├─ transform_rows()  normalize → extract → filter → cluster_id
         ├─ upsert_complaints()
         └─ prune_old_complaints()  (90-day retention)
                              │
                              ▼
              incident_service → public synthesis/redaction → TrafficMY UI
              static Rapid Rail GTFS → journey_service ───────┘
```

## Source lane priority (Malaysia reality)

| Priority | Lane | Role | Status |
|----------|------|------|--------|
| 1 | **Threads** | Primary social signal — Malaysians post transport complaints here first | Active — authenticated web search with public fallback |
| 2 | **Official** | Ground truth for RapidKL / KTMB / telco outages | Active — Playwright for MyRapid |
| 3 | **GTFS-RT** | Optional map/reference telemetry, never incident truth | Reference only |
| 4 | **Reddit** | Secondary social corroboration | Active |
| 5 | **RSS** | News syndication | Active — low volume |
| 6 | **X** | Tertiary social — dormant without auth | Dormant — accepts 0 rows |

**Design rule:** Threads is sensor input, not public copy. A protected browser session improves search coverage; native public Threads search remains the autonomous fallback. External search engines remain last-resort discovery.

## Data model

Single table `complaints` (SQLite):

- Identity: `source_platform`, `post_id` (unique upsert key)
- Internal content: `raw_text`, `normalized_text`, `url`, `author_handle`
- Extraction: `category`, `entity`, `location`, `state`, `subcategory`, `severity`
- Grouping: `cluster_id` — e.g. `transport:Kelana Jaya Line:Bangsar:delay`
- Timestamps: `created_at` (source), `inserted_at` (ingest)

Raw content exists only at the ingest/audit boundary. Public APIs remove raw text and handles and emit deterministic professional summaries plus source links.

## Ingest pipeline

### Full ingest (`run_ingest`)

1. Collect due lanes in parallel with independent run status/timing; GTFS and unauthenticated X are paused
2. Write raw sample to `data/raw/latest_sample.json`
3. `transform_rows()` applies platform-specific filters:
   - Social: complaint signal + category signal + entity rules for telco/banking
   - Official: `_official_grounding_ok` — rejects open-data brochure pages
   - GTFS: disabled for incident inference by default
4. Upsert + prune + write `data/reports/latest_ingest_summary.json`

### GTFS reference lane

Static GTFS supplies rail geometry/station routing and on-demand GTFS-RT can supply optional bus positions. `GTFS_ANOMALY_ENABLED=false` prevents scheduled vehicle-position inference from creating incident rows.

### Freshness window

- **Current line-status window:** 24 hours (`STATUS_WINDOW_HOURS`)
- **Evidence window:** 21 days (`LIVE_WINDOW_DAYS`)
- **Recent bucket:** ≤3 days
- **Aging:** 4–21 days
- **Stale:** >21 days (hidden from default TrafficMY view)

The line board never treats absence of public reports as confirmed normal service. It returns `No current signal`; only recent evidence can create a delay/disruption state. Planned services are returned separately from operational lines.

## Clustering & confidence

### Cluster ID construction

```
{category}:{entity}:{location}:{issue_key}
```

Fallback when sparse: `{category}:{source_platform}`

### Confidence scoring (`incident_service`)

Source weights: official 1.0, x 0.9, threads 0.85, gtfs_rt 0.85, reddit 0.8, rss 0.75

Score factors: volume, source diversity, severity, entity/location presence, official corroboration.

Bands: **strong** ≥5.5, **reasonable** ≥3.5, else **weak**.

Official rows are excluded from default cluster list but used for corroboration.

## Scheduler

Daemon thread `trafficmy-scheduler`, 30s tick:

| Job | Default interval | Function |
|-----|------------------|----------|
| GTFS anomaly | disabled | Reference-only unless explicitly enabled |
| Full | 900s | `run_ingest(respect_cadence=True)` |
| SQLite backup | 21600s | Online backup + 14-copy rotation |

Mutex lock keeps full ingest single-flight. Source cadence prevents slow empty lanes from running every cycle. Collector runs persist status, duration, row count, error, and last non-empty time.

Startup optional: `ADUANMY_REFRESH_ON_STARTUP=true` (enabled in production Docker).

## API surface

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | DB, ingest age, scheduler state |
| `GET /api/trafficmy/status` | Product freshness + ingest snapshot |
| `GET /api/trafficmy/config` | UI config (window, poll interval, source lanes) |
| `GET /api/trafficmy/overview` | Hero stats + entity/location chips |
| `GET /api/trafficmy/incidents` | Filtered incident list |
| `GET /api/trafficmy/incidents/{id}` | Drilldown evidence |
| `GET /api/trafficmy/journey/stations` | Search stations in the cached official Rapid Rail GTFS |
| `GET /api/trafficmy/journey/plan` | Rail-first route, interchanges, and estimated access walks |
| `GET /api/trafficmy/updates` | Source-linked, dated offers and service announcements |
| `GET /api/trafficmy/pass-comparison` | Estimated Rapid KL pass break-even comparison |
| `GET /api/health/live` | Process, DB, and scheduler liveness |
| `GET /api/health/ready` | Freshness-aware readiness |
| `POST /api/refresh` | Key-protected operator action; unavailable to normal visitors |

## Configuration

YAML configs in `configs/`:

| File | Purpose |
|------|---------|
| `discovery.yaml` | Queries, watchlists, RSS feeds — sliced by `ADUANMY_DISCOVERY_DEPTH` |
| `seed_urls.yaml` | Exact post URLs + profile discovery flags |
| `entities.yaml` | Entity allowlist for extraction |
| `locations.yaml` | Station/place → negeri mapping |
| `gtfs.yaml` | Prasarana API bases + anomaly thresholds |
| `transport_updates.yaml` | Dated passenger updates and concessions with source links |

Journey routing reads the official static Rapid Rail GTFS cached in `data/gtfs/cache/rapid-rail-kl.zip`. Landmark/address lookup uses Malaysia-filtered Nominatim search; walking distances are straight-line estimates, not turn-by-turn directions. LRT Shah Alam is shown as operating from 29 June 2026, but route planning will not include it until the official GTFS dataset publishes its stations and trips.

Environment (prefix `ADUANMY_`):

| Variable | Production | Purpose |
|----------|------------|---------|
| `DB_PATH` | `/data/aduanmy.db` | SQLite location |
| `DISCOVERY_DEPTH` | `full` | Query breadth |
| `FULL_REFRESH_INTERVAL_SECONDS` | `900` | Full ingest cadence |
| `GTFS_ANOMALY_ENABLED` | `false` | Keep telemetry out of incident truth |
| `REFRESH_ON_STARTUP` | `true` | Boot-time ingest |
| `ALLOW_DASHBOARD_REFRESH` | `false` | Visitors only reload snapshots |
| `REFRESH_API_KEY` | random | Protects refresh from external callers |
| `THREADS_SESSION_PATH` | `/data/private/threads-session.json` | Protected read-only browser session; optional |

## Deployment

```
Local: D:\aduanmy\
Deploy: python scripts/deploy_do.py  (paramiko → 68.183.181.237)
Remote: /root/trafficmy/ → Docker trafficmy :8002
Public: https://arifaqyl.me/traffic/  (nginx proxy)
Volume: trafficmy_data:/data  (persistent DB + reports)
```

Docker base: `mcr.microsoft.com/playwright/python:v1.49.0-jammy` — Playwright pinned to `==1.49.0`. Docker restart policy, `/api/health/live`, and a host systemd watchdog provide recovery independent of the developer PC.

## Threads collector architecture

```
collect_threads_sample()
  │
  ├─ 1. _collect_keyword_search_posts()     PRIMARY
  │      Single authenticated Playwright context, public fallback
  │      9 mandatory rail queries + 3 rotating national queries
  │      threads.com/search?q=<keyword>&filter=recent
  │      Parses relative times (4d, 16h) via date_hints
  │
  ├─ 2. _collect_latest_watchlist_posts()   if keyword < 6 rows
  │      News + commuter profiles from discovery.yaml
  │
  └─ 3. _collect_seed_posts()               fallback seeds
         Static URLs + profile discovery (skipped when keyword ≥ 6)
```

Filters: signup bait, aggregated feed blobs, reply-thread blobs, generic opinions, nostalgia, habitual complaints, speculative questions, and foreign-platform outages in telco queries. A rider message must contain observable operational value such as current impact, direct experience, measured delay, or a concrete cause; a line name plus `delay/problem` is insufficient.
Threads results must have a usable timestamp and be no older than 72 hours before ingest. Public current-status surfaces apply a stricter 24-hour window.

## X collector architecture (dormant lane)

```
collect_x_sample()
  │
  ├─ Seed status URLs (HTTP + fxtwitter API)
  ├─ Profile discovery via syndication API (fast)
  ├─ Playwright profile scrape ONLY if syndication shows recent statuses
  └─ Bing site:x.com search (full depth only)
```

Without X login, public timelines stop at ~Apr 2025 for @askrapidkl. Transport is covered by official + threads.

## Non-goals (current phase)

- National truth engine / verified incident database
- Login-heavy scraping on every lane (Threads alone may use a protected read-only browser session)
- Generic multi-category complaint platform UI
- AI classification on every refresh
- Postgres / Redis / job queue (SQLite + single container is sufficient)

## Roadmap hooks

- Automatic Threads session-health warning and operator refresh workflow
- Manual status ID injection workflow for breaking incidents
- Map view + timeline visualization
- Severity-based alerting
- Telco wedge product (second surface after transport)
