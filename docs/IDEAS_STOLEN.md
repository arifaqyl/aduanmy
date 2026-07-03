# TrafficMY — Ideas Stolen (brainstorm ledger)

Cross-product research → what we borrowed, what shipped, and what we skipped. Malaysia transport scope only; real data only.

| Source | Idea stolen | Shipped | Why |
|--------|-------------|---------|-----|
| **TfL Line Status** | Line board first, severity badges + text, short-lived status window | Y | Core product — trust-first grid |
| **SuperNYC** | Methodology footer, stale-data banner, honest “no recent reports” | Y | Already in product; kept as hero pattern |
| **Citymapper** | Mode icons per line, disruption chips, fusion of sources | Y | OSS Tabler icons + pulse strip |
| **Moovit** | “Why delayed?” reason text on row | Y | `reason` field on line rows |
| **Transit.app** | Progressive disclosure — summary → evidence drawer | Y | Row tap → incident panel |
| **Google Maps transit** | Layer toggles (rail vs bus honesty) | Partial | Map tab: rail markers; bus = honest placeholder |
| **Rome2Rio** | Multi-leg plan + fare band hint with disclaimer | Y | Plan tab + `fares.json` estimate |
| **MyRapid Pulse / KTMB** | Operator line colours, service alert feel | Y | `LINE_COLORS`, official corroboration badge |
| **Trainline / National Rail** | Incident timeline in detail view | Y | Chronological posts in drawer |
| **HK MTR / Yahoo Transit JP** | Dense but scannable rows, time context | Y | Health score + rush-hour pill |
| **Down Detector** | Volume spike = something may be wrong | Y | Report count badge + health score |
| **Waze** | Freshness timestamps, stale labelled | Y | MYT timestamps, stale banner |
| **Grab / inDrive** | Simple From → To + swap | Y | Plan tab journey form |
| **RISECURE (WMATA)** | Saved lines / notify on change | Partial | My lines + explicitly open-tab browser watch; server push is not claimed |
| **MapLibre / OpenFreeMap** | Malaysia-bounded vector map, 3D buildings, station popups | Y | GPU map tab, line geometry, interchanges, optional reference telemetry |
| **OpenTripPlanner** | Full multi-agency OTP routing | N | No OTP in repo; rail GTFS graph only |
| **Live train map (GTFS-RT rail)** | Moving train dots | N | No rail GTFS-RT; would be fake |
| **Compare lines side-by-side** | Two-line diff panel | N | Scope; board sort covers glance need |
| **OG image share cards** | Auto-generated social preview | N | Text/Web Share API sufficient for v1 |
| **Station detail sheet (full)** | All lines at station from graph | Partial | Map popup + search filter |
| **7-day alert history API** | Per-line timeline endpoint | Partial | Drawer shows cluster posts; no 7d aggregate API yet |
| **High contrast / reduced motion** | A11y toggles | Y | Header toggle + `prefers-reduced-motion` |
| **Quiet line vs no data** | Distinct empty semantics | Y | `empty_state`: quiet / no_data |
| **Confidence meter** | weak / reasonable / strong bands | Y | On report cards from API |
| **Official vs social strips** | Separate corroborated lane | Y | Official strip above social feed |
| **Schematic route strip** | Non-geographic line diagram | Y | Coloured stripe + legend on row |
| **My50 / pass comparison** | Break-even calculator | Y | Passes tab (existing API) |
| **Happening now offers grid** | Operator promos | Y | Collapsible under Status tab |

| **Interactive KV schematic** | Tap line on stylised diagram → scroll to row | Y | Inline SVG, TfL/Citymapper-inspired |
| **Stats bar explainer** | Tap tracked-lines summary → sheet | Y | 16 lines · rail/bus split · active alerts |
| **Refresh copy clarity** | Page refresh vs full scan pills | Y | Desktop pills + mobile one-liner + (i) popover |
| **Honest silence semantics** | Missing crowd reports are unknown, not normal | Y | `status: unknown`, `empty_state: no_data`, `board_summary` |
| **Bus map honesty card** | Replace vague "soon" with why | Y | Expandable explainer on Map tab |
| **Health ring on line icon** | SVG dash ring from health score | Y | Pulse.app / Citymapper glance pattern |
| **Severity edge pulse** | Animate only delay/disruption rows | Y | `prefers-reduced-motion` respected |
| **Tab SVG icons** | Status/Map/Plan/Passes icons | Y | Small inline SVG per tab |

## Shipped feature set (this release)

1. Status board hero (TfL) + pulse disruption strip (Citymapper)
2. Line health score 0–100 (Down Detector + Waze freshness)
3. Quiet line vs no data labels (SuperNYC honesty)
4. Confidence bands on reports (Moovit/Transit)
5. Official corroboration strip (Citymapper fusion)
6. Rush hour MYT context (HK MRT density)
7. Map tab — MapLibre vector canvas, Malaysia bounds, 3D city view, official rail geometry
8. Plan tab — journey API + Rome2Rio fare hint
9. Passes tab — Rapid KL comparison
10. Saved lines + open-tab watch (RISECURE); no false background-push promise
11. Incident timeline in drawer (Trainline)
12. High contrast toggle (a11y)
13. Favourites, share, search, sort (prior release, retained)
14. **Interactive KV schematic** — tap line → scroll to board row
15. **Stats bar** — lines tracked / rail / bus / active alerts (tap for explainer)
16. **All-clear board summary** — `board_summary` when zero active alerts
17. **24h status window** — disruption claims expire quickly; evidence remains available separately
18. **Refresh meta copy** — page refresh vs data scrape, mobile-friendly
19. **Bus map explainer** — honest why rail-first
20. **Health ring + severity pulse** — polish on active rows only
21. **Status tab ? help** — crowd-reported vs official RapidKL

## Needs real API / data later

- Bus stop map layer (GTFS static bus feeds per city)
- Live rail vehicle positions (GTFS-RT rail from Prasarana/KTMB)
- Exact zone-based fares (MyRapid fare table API)
- Push subscriptions server-side (saved lines across devices)
- 7-day per-line incident history endpoint
