# AduanMY / TrafficMY

Malaysia-first public transport pulse built from rider and operator signals.

**Live:** [arifaqyl.me/traffic](https://arifaqyl.me/traffic/)  
**Status:** production · **Tests:** 236 passing · **License:** [MIT](LICENSE)

AduanMY is the research engine. **TrafficMY** is the shipped product surface: a mobile-first PWA that turns filtered crowd and official signals into line status, live incidents, maps, and journey helpers for Malaysian public transport.

## What It Does

Production loop:

`collect → reject noise → normalize → cluster → corroborate → professional public summary`

TrafficMY focuses on:
- nationwide public transport disruption signals (KV, KTM, Penang, Johor, east MY)
- station, line, and negeri extraction with strict freshness gates
- 15-minute unattended collection, per-source health, 90-day history, rotating SQLite backups
- official grounding (MyRapid + KTMB) without treating operators as automatic all-clear
- Stitch Play UI: glance card, live feed, MapLibre map, travel planner, installable PWA

## Trust Boundary

- A rider post is an early signal, never automatic truth.
- `No current signal` is not an all-clear.
- Raw posts and handles stay internal; public output is synthesized and source-linked.
- GTFS never confirms an incident.
- Official operator channels remain the final travel check.

## Current Source Strategy

| Source | Role |
|--------|------|
| Threads | Primary rider-signal lane (authenticated search + public fallback) |
| Reddit | Secondary lane, two-hour minimum cadence |
| RSS | Malaysian transport headlines |
| Official / open data | Grounding and verification only |
| X | Paused in unattended mode until authenticated |
| GTFS static | Journey/map reference only; anomaly inference disabled |

## API Surface

- `GET /api/trafficmy/signals/today` — **B2B/embed prototype**: today’s rider signals + line board (JSON v1)
- `GET /developers` · `GET /embed` — human docs + iframe widget
- `GET /api/health` · `GET /api/health/live` · `GET /api/health/ready`
- `GET /api/trafficmy/overview` · `GET /api/trafficmy/status`
- `GET /api/trafficmy/incidents` · `GET /api/trafficmy/incidents/{cluster_id}`
- `GET /api/trafficmy/lines` · `GET /api/trafficmy/map/live`
- `GET /api/trafficmy/lines/{line_id}/history` — 14-day rider-signal trend, "is this normal?"
- `GET /api/trafficmy/journey/plan`
- `POST /api/refresh` (API key in production)

### Positioning

TrafficMY is **live rider intelligence for today (MYT)** — not a ridership analytics dashboard. For historical passenger counts and DOSM-style trends, use official open-data products; for “is something wrong on my line right now?” use TrafficMY.

Full route list and architecture notes: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## Local Setup

```bash
cd D:\aduanmy
pip install -e .[dev]
python -m pytest tests -q
uvicorn app.main:app --reload --port 8000
```

Open `http://127.0.0.1:8000/`

## Docker Deploy

```bash
docker compose up --build -d
```

Open `http://localhost:8002/`. Data persists in the `trafficmy_data` volume.

Key environment knobs (see [.env.example](.env.example)):

- `ADUANMY_FULL_REFRESH_INTERVAL_SECONDS` — background collection interval
- `ADUANMY_REFRESH_API_KEY` — protect `POST /api/refresh`
- `ADUANMY_THREADS_SESSION_PATH` — optional Playwright session (public search remains fallback)
- `ADUANMY_GTFS_ANOMALY_ENABLED` — keep `false`

## Repository Structure

```text
app/           FastAPI routes, collectors, pipeline, services
configs/       categories, entities, queries, GTFS, discovery
static/        Stitch Play UI (HTML/CSS/JS, mascots, map assets)
scripts/       deploy, snapshot, reporting
tests/         regression coverage (236 tests)
docs/          architecture, production audit, transport reference
```

## Useful Commands

```bash
python -m pytest tests -q
python scripts/run_snapshot.py
python scripts/audit_sources.py
pip-audit -r requirements.production.txt
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Production audit (2026-06-30)](docs/PRODUCTION_AUDIT_2026-06-30.md)
- [Malaysia transport reference](docs/MALAYSIA_TRANSPORT_REFERENCE.md)
- [Roadmap](ROADMAP.md)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## Author

**Arif Aqyl** — Backend developer · live products · Malaysia

- Portfolio: [arifaqyl.me](https://arifaqyl.me)
- LinkedIn: [linkedin.com/in/arifaqyl](https://linkedin.com/in/arifaqyl)
- X: [@mindofaqyl](https://x.com/mindofaqyl)
- Email: [hello@arifaqyl.me](mailto:hello@arifaqyl.me)

## License

[MIT](LICENSE)
