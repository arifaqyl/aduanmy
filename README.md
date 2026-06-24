# AduanMY

Malaysia-first public complaint intelligence engine.

Status: `in progress`

Current product direction: **TrafficMY**  
Why: transport has the strongest live complaint density, the clearest verification path, and the best demo story in the current evidence set.

## What It Does

AduanMY collects public complaint signals from multiple sources, normalizes them, clusters duplicate incidents, and exposes a cleaner surface for deciding which Malaysian problem area is worth productizing.

The current repo is not a generic “social listening” toy.  
It is a source-backed decision engine with a live transport-focused surface.

Core loop:

`collect -> filter -> normalize -> cluster -> score -> choose the wedge`

## Current Wedge

The broad project is `AduanMY`.  
The current strongest wedge is `TrafficMY`.

TrafficMY focuses on:
- public transport disruption signals
- station and line extraction
- freshness-aware incident surfacing
- official grounding without pretending official sources are enough on their own

## Current Source Strategy

- Threads: strongest current public social lane
- Reddit: useful, but noisier
- X: narrow targeted service-account monitoring
- Official/open data: grounding and verification only

Current official reality:
- MyRapid detail pages are often Imperva-blocked to plain HTTP fetches
- MyRapid homepage and lightweight alert harvesting are still usable
- Malaysia open-data GTFS-Realtime is useful context, but not yet a full rail incident truth source for this use case

## Verified Current State

- tests: `97/97` passing
- live routes exist for refresh, overview, status, incidents, and incident detail
- source freshness is tracked from event timestamps when available
- official rows are separated from crowd signals in scoring logic
- stale signals are hidden by default and exposed only when explicitly requested

Recent verified ingest shape:
- raw Threads rows: `5`
- raw Reddit rows: `5`
- raw X rows: `1`
- raw official rows: `9`
- written rows after filtering: `14`

Current wedge ranking:
1. `transport`
2. `telco_internet`
3. everything else trails materially

## API Surface

- `GET /api/health`
- `GET /api/complaints`
- `GET /api/clusters`
- `GET /api/clusters/{cluster_id}`
- `GET /api/scores`
- `GET /api/trends`
- `POST /api/refresh`
- `GET /api/trafficmy/overview`
- `GET /api/trafficmy/status`
- `GET /api/trafficmy/incidents`
- `GET /api/trafficmy/incidents/{cluster_id}`

## Local Setup

```bash
cd D:\aduanmy
pip install -e .[dev]
python -m pytest tests -q
uvicorn app.main:app --reload --port 8000
```

Open:

- `http://127.0.0.1:8000/`

Optional for better public-page collection:

```bash
pip install playwright
playwright install chromium
```

## Useful Commands

```bash
python -m pytest tests -q
python scripts/run_snapshot.py
python scripts/audit_sources.py
python scripts/generate_trend_report.py
```

## Repository Structure

```text
app/
  api/             FastAPI routes
  collectors/      Threads, Reddit, X, official collectors
  pipeline/        normalization, extraction, dedup
  services/        ingest, scoring, incidents, trends, overview
  db/              SQLite session and schema helpers
configs/           categories, entities, queries, seed URLs
data/reports/      generated reports and decision artifacts
scripts/           snapshot and reporting scripts
tests/             regression coverage
static/            lightweight frontend
```

## What This Repo Is Not Claiming

- not a complete Malaysian incident truth layer
- not a stable rail telemetry platform yet
- not a replacement for official service-alert infrastructure
- not a finished public product

The current repo is best understood as:
- a real collection-and-decision engine
- with a credible transport wedge
- still being hardened source by source

## Main Technical Decisions

- FastAPI + SQLite for local-first iteration
- narrow collectors over giant crawler frameworks
- exact seeds and strict filters over broad noisy scraping
- official sources used for grounding, not inflated complaint density
- product freshness derived from source event time where possible

## Known Limitations

- Threads is strong but still brittle
- X discovery is narrow without account-backed expansion
- Reddit is usable but still noisy
- official rail alert coverage is incomplete
- MyRapid anti-bot protections limit plain-fetch detail scraping

## Near-Term Roadmap

See [ROADMAP.md](ROADMAP.md).

Current priorities:
- improve transport truth quality
- tighten telco false-positive handling
- strengthen official transport status ingestion
- keep sharpening TrafficMY instead of drifting into a generic category dump

## Reports

Useful generated artifacts:
- `data/reports/decision_memo.md`
- `data/reports/source-capability-matrix.md`
- `data/reports/source_audit_snapshot.md`
- `data/reports/latest_trends.md`

## License

[MIT](LICENSE)
