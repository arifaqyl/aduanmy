# AduanMY

Status: `in progress`

Malaysia-first public complaint intelligence engine.

Goal:

`collect -> test -> compare -> choose`

This project ingests public complaint signals from Threads, Reddit, X, and official/open-data sources, then scores which Malaysian problem categories have the best density, verification potential, and product value.

## Phase 1 Scope

- source capability audit
- structured complaint storage
- category/entity/location extraction
- duplicate clustering
- category scorecard
- decision memo for the best product wedge

## Initial Categories

- transport
- telco_internet
- banking_payments
- gov_portals
- flood_weather
- healthcare
- cost_of_living
- housing_city
- education

## Initial Sources

- Threads
- Reddit
- X
- official/open data

## Current collection posture

- Reddit: `old.reddit.com` HTML search with anchor-token relevance filtering
- Threads: exact public post scraping with selective Playwright timestamp extraction
- X: targeted public service-account profile discovery plus exact status-page fetches
- Official/open data: direct public page collection, limited to fetchable grounding pages

## Current Status

- scaffold created
- FastAPI health route works
- first config files added
- first real sample ingest works across Threads, Reddit, X, and official pages
- current verified ingest snapshot:
  - raw Threads rows: `5`
  - raw Reddit rows: `4`
  - raw X rows: `1`
  - raw official rows: `6`
  - stored rows after filtering: `12` total
  - promoted social complaint rows: `10`
  - social category mix after filtering: `transport 7`, `telco_internet 3`
  - current official grounding rows that survive into the DB:
    - `Ampang/Sri Petaling Line`
    - `Unifi outage`
  - recent collector timings observed in the latest live summary: `threads ~29s`, `reddit ~26s`, `x ~14s`, `official ~35s`
- tests: `97/97` passing
- live trend surfaces added:
  - `GET /api/trends`
  - `scripts/generate_trend_report.py`
- product-shaped demo surfaces now exist:
  - `POST /api/refresh`
  - `GET /api/trafficmy/overview`
  - `GET /api/trafficmy/status`
  - `GET /api/trafficmy/incidents`
  - `GET /api/trafficmy/incidents/{cluster_id}`

## Verified Phase 1 Reality

- Threads is now the strongest live social source in the repo:
  - exact seed complaint posts work
  - exact post pages now yield real `created_at` timestamps through Playwright
  - the current transport Threads lane now disables profile discovery for the live seed set because the broad pass was mostly low-value noise
  - the transport lane now prefers exact known-good rail disruption posts over noisy profile scraping
- Reddit works, but quality is mixed:
  - `old.reddit.com` HTML search is viable
  - the public `.json` path is blocked with `403`
  - search results and curated exact posts now expose real Reddit timestamps
  - a curated exact-post seed lane now preserves real outage evidence when search quality drifts
  - the Reddit lane is now narrower on purpose:
    - fewer high-signal discovery queries
    - one exact current transport seed to stabilize live freshness
  - generic telco junk is now filtered earlier, so the raw Reddit lane is much narrower than before
  - the transport seed now trims subreddit boilerplate instead of storing sidebar sludge
  - curated exact seeds can carry source-time fallback metadata, so product freshness does not silently degrade when Reddit exact-page fetches are throttled
- X is still weak:
  - public search is still weak and gated
  - current posture is now recent-only, not archive-friendly
  - old seed statuses are filtered out if they fall outside the recency window
  - the repo now prefers current profile/search discovery and only keeps recent status rows
  - current verified live X lane is `1` recent row, which is smaller but avoids replaying stale incident history
- the status surface is now more honest:
  - freshness is based on source `created_at` when available, not just "we scraped recently"
  - if the latest evidence is old, the product now marks itself stale even when ingest is recent
  - the latest verified source event in the current live product is now `2026-06-24`
- the incident surface now exposes freshness semantics per cluster:
  - `recent`
  - `aging`
  - `stale`
  - shared freshness thresholds now drive both overview inclusion and per-cluster labeling
  - the default UI stays recent-only, while the stale toggle exposes older evidence explicitly
  - timestamp backfill now runs across all collected Threads rows, not only exact seed rows
- source-aware fallback now labels anonymous Rapid KL service replies as `RapidKL`, so the cluster surface no longer shows a generic `transport:delay`
- clusters now carry a confidence layer inspired by incident/news trackers:
  - `source_count`
  - `source_weight_total`
  - `corroborated_by_official`
  - `confidence_score`
  - `confidence_band`
  - `source_roles`
    - `public_signal`
    - `media_report`
    - `official_grounding`
  - official corroboration is now strict, not category-wide handwaving
  - media-only Threads incidents now surface as `media_report` instead of pretending to also be `public_signal`
- Official sources are useful for grounding and verification, not complaint density
- The official lane is now narrower and more honest:
  - MyRapid homepage alert harvesting now uses a lighter homepage-only pass instead of expensive detail-page fetches
  - when that homepage pass flakes, the collector now falls back to exact known MyRapid alert URLs/titles from current verified live fetches instead of silently dropping transport grounding
  - retry budgets are capped harder so Imperva failures do not burn a full ingest window
  - direct fetches of `myrapid.com.my/pulse/service-alerts-on-pulse/` and detail alert URLs still return Imperva/Incapsula shell pages (`_Incapsula_Resource`, `noindex,nofollow`) to plain HTTP requests, so the repo does not pretend those pages are stably scrapeable
  - generic official reference pages and route-less MyRapid traffic/bus titles no longer get promoted into the complaints DB
  - current live DB promotion is strict enough that only operationally relevant official rows survive
  - official `data.gov.my` GTFS-Realtime does not yet give us the rail alert truth we would want:
    - official docs currently say GTFS-R only offers vehicle positions
    - `rapid-rail-kl` does not yet have stable realtime feeds for the alert use case
  - official rows are forced to `low` severity so they do not pretend to be incidents
- Scoring and trend reports now separate social complaint density from official grounding:
  - social rows drive top categories, entities, locations, and wedge scoring density
  - official rows stay in reports as verification rails only
- Cluster output is now more trustworthy:
  - cluster severity uses explicit severity ranking instead of lexical string ordering
  - transport station extraction now catches `MRT Maluri`, which improves station-level grouping
  - transport entity extraction now prefers specific rail lines over generic `LRT`, including:
    - `Ampang/Sri Petaling Line`
    - `Kelana Jaya Line`
  - station-level location extraction now captures named stations in the delay posts instead of collapsing them into the generic line name
  - multi-line MRT wording such as `Putrajaya, Kajang MRT lines` no longer collapses to vague `MRT`; it now surfaces as `Kajang/Putrajaya Lines`
  - line-update titles like `Kemas Kini Laluan Ampang/Sri Petaling` no longer get misread as station location `Ampang`
  - the main cluster surface now excludes official grounding rows by default, so incident views stay complaint-first
  - generic transport history/discussion posts no longer leak in just because they mention `bus` or `Kuala Lumpur`

## Next Immediate Work

1. tighten remaining telco precision further around non-outage support/app-rant noise
2. improve cluster quality beyond simple entity/location grouping
3. keep sharpening `TrafficMY` instead of drifting back to broad AduanMY

## First Snapshot

From the latest verified ingest run:

- `transport` is the strongest current wedge
- `telco_internet` is second and still strong
- `gov_portals` and `flood_weather` are currently out of the promoted live snapshot after stricter gating
- `banking_payments` dropped out of the current verified snapshot after stricter filtering
- the decision lane is now clear enough that `TrafficMY` is the current default next product wedge
- the cleanest current product candidates are:
  - `TrafficMY`
  - `ServiceOutageMY`
  - `PortalWatchMY`

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

## TrafficMY Surface

- `POST /api/refresh`
  - run ingest and return latest summary plus cluster count
- `GET /api/trafficmy/overview`
  - product summary, top incidents, top transport entities/locations
- `GET /api/trafficmy/status`
  - last ingest freshness, latest complaint timestamps, transport cluster count, top wedge score
- `GET /api/trafficmy/incidents`
  - transport-only incident list with:
    - `sort_by=strongest|freshest`
    - `confidence_band`
    - `severity`
    - `entity`
    - `location`
- `GET /api/trafficmy/incidents/{cluster_id}`
  - TrafficMY-native incident detail payload with evidence rows and source breakdown

Current reality:
- this route is frontend-ready
- the default live surface currently shows `3` transport incident clusters inside the current `21`-day live window and hides `4` stale ones
- `GET /api/trafficmy/overview?include_stale=true` and the frontend stale toggle expose `7` total transport clusters when older evidence is explicitly requested
- none currently score as `strong`
- the default live surface now shows `3` `reasonable` incidents and `0` `weak`
- the strongest live transport incidents right now are:
  - `Kelana Jaya Line / Pasar Seni`
  - `MRT Maluri`
  - `Kelana Jaya Line / Dang Wangi`
- the default strongest sort is now recent-first within the same confidence band, so fresh incidents no longer lose to older near-tie rows
- the current top wedge score is `15`
- stale-inclusive transport cluster examples currently include:
  - `MRT Maluri`
  - `Ampang/Sri Petaling Line / Chan Sow Lin`
  - `LRT Ara Damansara`
  - `Kajang/Putrajaya Lines`

## Useful Commands

- `python -m pytest tests -q`
- `python scripts/run_snapshot.py`
- `python scripts/audit_sources.py`
- `python scripts/generate_trend_report.py`

## Notes

- Tests now run against isolated temporary SQLite files instead of mutating the live local dataset.
- Threads discovery is filtered at the profile-page preview level before deeper post fetches, which cuts wasted fetches and keeps more relevant complaint signals.
- The current transport Threads posture goes further: profile discovery is disabled for the live seed set, which cut the raw Threads lane from `11` to `5` and reduced collector time from about `63s` to about `27s` on the latest verified refresh.
- Slash-bearing transport cluster IDs such as `Ampang/Sri Petaling Line` now resolve correctly through the TrafficMY detail route instead of failing at the router layer.
- Reddit exact current transport seeds now preserve fallback `created_at` and author metadata, which keeps the status surface aligned with the best known source event under throttle.
- Reddit exact transport extraction now also enriches weak post bodies from linked articles, which upgraded the fresh current signal from a generic `Kelana Jaya Line / delay` row into the more useful `Kelana Jaya Line / Pasar Seni` incident.
- Reddit multi-line MRT wording now also stays line-specific, which upgraded the stale generic `transport:MRT:delay` cluster into `transport:Kajang/Putrajaya Lines:delay`.
- `scripts/run_snapshot.py` is the stable report path: one ingest run, then both markdown reports from the same evidence set.
- `.github/workflows/snapshot.yml` now provides a scraper-only refresh lane every 6 hours, so freshness does not depend on spending LLM tokens.
- The X lane now stays stable by anchoring on curated exact status posts with fallback text, instead of depending on broad profile discovery every run.
- Trend terms now suppress more support-reply filler so the report reads more like incidents and less like status-page boilerplate.
- Cluster summaries now preserve the highest real severity for mixed-source incidents instead of returning a wrong lexical max.
- The cluster surface now hides official grounding rows by default, which keeps the incident list aligned with the TrafficMY story.
- The overview and incidents surfaces now support explicit stale inclusion while keeping the default product view recent-first.
- Cluster payloads now expose `freshness_bucket` and `age_days`, so the UI can show whether a signal is recent, aging, or stale instead of pretending everything is equally live.
- Freshness thresholds are now centralized, so default live inclusion and `recent/aging/stale` labels cannot silently drift apart.
- Tests now isolate both the SQLite DB and generated `data/` artifacts, so verification runs no longer overwrite the live snapshot files.
- Reddit now has a curated exact-post fallback lane for known-good outage posts, which keeps telco evidence alive without reopening the earlier junk flood.
- The repo default now reflects reality:
  - `reddit_provider` is `public_html`, not `public_json`
  - the stale zero-byte `data/complaints.db` artifact was removed
- The X lane now drops stale archival statuses, so the live product surface is thinner but more truthful.
