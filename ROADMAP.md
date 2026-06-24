# Roadmap

## Current Phase

Phase 1: prove the collection engine, score the categories, and narrow to the strongest wedge.

Current winner: `TrafficMY`

## Now

- [x] Multi-source collection across Threads, Reddit, X, and official pages
- [x] Structured storage in SQLite
- [x] Category, entity, location extraction
- [x] Duplicate clustering
- [x] Wedge scoring
- [x] Transport-focused product routes
- [x] Freshness-aware incident surfacing
- [x] Official grounding separated from crowd density

## Next

- [ ] Tighten telco false positives further
- [ ] Improve official transport status harvesting
- [ ] Improve cluster labeling and issue typing
- [ ] Expand fresh transport discovery without reopening noise
- [ ] Make the frontend incident story sharper

## Later

- [ ] Session-backed X expansion behind a controlled flag
- [ ] Better transport anomaly detection from official/open-data telemetry where feasible
- [ ] Provider/entity dashboards
- [ ] Timeline views for recurring incidents
- [ ] Clearer scoring/report exports for wedge comparison

## Explicit Non-Goals For Now

- [ ] Broad national “truth engine” claims
- [ ] Login-heavy scraping everywhere
- [ ] Full generic complaint platform UI
- [ ] Corruption accusation mapping
- [ ] Expensive always-on AI classification for every refresh
