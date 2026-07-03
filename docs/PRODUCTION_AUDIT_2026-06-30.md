# TrafficMY production audit — 30 June 2026

## Product contract

TrafficMY is a Malaysia transport pulse, not a social-feed mirror. Public rider posts are sensor input. The public product emits a cautious incident headline, structured summary, time, affected service/place, confidence context, and source link. It never republishes raw wording or usernames.

`No current signal` means no recent evidence passed the filter. It never means normal service is confirmed.

## Research decisions

| Evidence | Decision in TrafficMY |
|---|---|
| The reviewed `yarn-threads-cli` demonstrates local browser-cookie extraction, but its search command only finds users, not posts ([repository](https://github.com/jeizzon/yarn-threads-cli)). The older unofficial API client is archived ([repository](https://github.com/Danie1/threads-api)). | Reuse the cookie-session pattern, not either dependency: TrafficMY performs its own narrow, read-only Threads post search and falls back to public search automatically. |
| GTFS Realtime expects vehicle/trip data under 90 seconds and alerts under 10 minutes ([GTFS best practices](https://gtfs.org/documentation/realtime/realtime-best-practices/)) | The available Malaysia vehicle feed is map/reference telemetry only. Scheduled GTFS anomaly inference is disabled and cannot determine incident truth. |
| Citymapper provides commute-specific alerts, automatic commute context, disruption-aware routing, and offline support ([commute alerts](https://citymapper.com/news/858/you-asked-for-bad-news-good-news-we-have-it), [SmartCommute](https://citymapper.com/news/1039/the-smartcommute-tm), [route around disruption](https://citymapper.com/news/495/route-around-disruptions), [offline](https://citymapper.com/news/1282/offline-support)) | Saved lines, line-first scanning, explicit disruption state, PWA shell, and journey context; no fake routing around unconfirmed incidents. |
| Moovit combines favorites, live navigation, real-time alerts, and crowd reports ([features](https://moovit.com/features/)) | Rider input is treated as evidence, not publication-ready copy. Favorites remain local and tab-watch notifications are explicitly limited to an open tab. |
| MapLibre supports native 3D building extrusion ([official example](https://maplibre.org/maplibre-gl-js/docs/examples/display-buildings-in-3d/)); OpenFreeMap provides keyless vector styles ([quick start](https://openfreemap.org/quick_start/) | GPU vector map, official rail geometry, interchange markers, optional bus reference telemetry, pitched 3D city view. |
| Service workers can supply an offline application shell ([web.dev](https://web.dev/learn/pwa/service-workers)) | Installable PWA caches shell/static assets only. Live status APIs remain network-only so stale incidents are never presented as live. |

The inspected community `Threads-Scraper` repository was rejected as a production dependency: its advertised entrypoint imports missing local modules and it has no regression suite. `yarn-threads-cli` was also rejected as a runtime dependency because it does not implement post search and its local test/audit baseline was unsuitable. TrafficMY keeps only the useful session pattern in a narrow collector it owns.

## Audit findings and fixes

| Previous failure mode | Production fix |
|---|---|
| Speculative posts such as questions about whether a train might have a problem became delays | Negative/speculative language gates plus present-tense and direct-rider evidence requirements. |
| Old operator notices could corroborate a new rider post | Official corroboration must be within 24 hours of the social signal. |
| Raw rider copy and handles were exposed | Public synthesis/redaction boundary applied to overview, line, incident detail, legacy complaint, and map payloads. |
| GTFS data could keep the product looking fresh or create incidents | Product freshness follows collector checks and public/official evidence separately; GTFS anomaly collection defaults off. |
| Slow/empty X and Reddit lanes ran on every refresh | X is paused until authenticated; Reddit runs at a two-hour minimum cadence. All lanes record independent status, duration, and last non-empty time. |
| Public refresh could start expensive scraping | The dashboard only reloads snapshots. Operator refresh requires a key; unattended collection runs in the scheduler. |
| A failed process could remain degraded indefinitely | Liveness/readiness endpoints, Docker healthcheck, restart policy, and a two-minute host watchdog. |
| SQLite/report writes could be left inconsistent | SQLite online backups every six hours, 14-copy rotation, and atomic JSON snapshots. |
| Dense desktop UI became a wall of 17 services on mobile | Active/saved services first; quiet network directory collapses on mobile; fixed bottom navigation and compact source health. |
| Recent Threads results still included generic opinions and discussion-only posts | Added a Threads-only rider-value gate requiring current observable impact, direct experience, a measured delay, or a concrete operational cause before storage. |

## Runtime model

- Full source collection every 15 minutes, off-request.
- Threads `Recent` search with nine mandatory rail queries (RapidKL, both LRT branches, both MRT lines, Monorail, LRT3/Shah Alam, KTM Komuter) plus three rotating Malaysia transport queries.
- Protected authenticated Threads web search when a valid session exists; public Threads search fallback otherwise.
- Independent source-run records; slow or empty sources remain observable.
- 24-hour status window and 21-day evidence window.
- 90-day data retention and six-hour database backups.
- Raw source material remains internal for classification/audit; public APIs expose professional summaries and source links only.

## Verified on 30 June 2026

- Real local ingest: Threads 6, official 13, Reddit 1, RSS 1; X paused by policy.
- Desktop and 375 px mobile browser QA: status, collapsed network directory, route planning, MapLibre canvas, 3D toggle, and subpath-safe assets.
- Browser console: zero errors and zero warnings after final map pass.
- PWA manifest and service worker: HTTP 200.
- Public incident endpoint scan: no `raw_text`, `example_text`, or author fields.
- Automated suite: 212 tests passing after the 1 July authenticated-recent value-gate update.

## Honest remaining dependency

Authenticated coverage depends on a valid local Threads browser session, which can expire. TrafficMY never blocks on it: every scheduled run falls back to public web search, and source health exposes the lane state instead of pretending success. The session file is excluded from source control and deployment archives, stored separately with owner-only permissions, and used only for read operations.
