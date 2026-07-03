# Roadmap

## Current Phase

**TrafficMY production** — live transport pulse with Stitch UI, strict scraper accuracy, and unattended droplet deploy.

Live: [arifaqyl.me/traffic](https://arifaqyl.me/traffic/)

## Shipped

- [x] Multi-source collection (Threads, Reddit, RSS, official)
- [x] Structured SQLite storage with 90-day retention and backups
- [x] Category, entity, location extraction with noise gates
- [x] Transport-focused product routes and professional public summaries
- [x] MYT calendar-day freshness model and end-of-service line states
- [x] MapLibre map, journey planner, pass calculator, installable PWA
- [x] Stitch Play UI (mascots, glance card, bottom nav, travel banner)
- [x] Docker production deploy with scheduler, healthchecks, watchdog
- [x] 227-test regression suite + CI on push/PR

## Next

- [ ] Saved commute watch (origin → destination alerts)
- [ ] Penang scope toggle
- [ ] Session-backed X lane behind a controlled flag
- [ ] Labelled incident-quality evaluation harness
- [ ] Further scraper precision (ambiguous place names, numeric route collisions)

## Explicit Non-Goals

- Broad national “truth engine” claims
- Republishing raw rider wording or usernames
- GTFS-as-incident-truth
- Login-heavy scraping everywhere

See [docs/PRODUCTION_AUDIT_2026-06-30.md](docs/PRODUCTION_AUDIT_2026-06-30.md) for the production baseline.
