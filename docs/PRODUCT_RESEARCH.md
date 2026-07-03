# TrafficMY — Global UX Research, Malaysia Product Scope

How the **web** surfaces transit disruption worldwide — patterns TrafficMY borrows for **Malaysia transport only** (LRT, MRT, KTM, ECRL, bas, LRT3, RTS, etc.). Not Singapore, Thailand, or other countries in our data or display.

**Product scope:** Malaysia nationwide public transport. **UX inspiration:** TfL, SuperNYC, Citymapper, Transit.app (global best practice).

## June 2026 production research update

- Meta's supported Threads platform exposes recent keyword search with a dedicated permission, query/time bounds, and pagination: [official workspace](https://www.postman.com/meta/threads/overview), [keyword-search request](https://www.postman.com/meta/threads/request/34203612-b3b2c12a-7ce6-4d86-a3c6-6d31e3b66ea1). TrafficMY uses this lane when credentialed and retains native search as an automatic fallback.
- Citymapper's strongest transferable patterns are commute-specific disruption notifications, an automatic commute dashboard, disruption-aware routing, and offline support: [alerts](https://citymapper.com/news/858/you-asked-for-bad-news-good-news-we-have-it), [SmartCommute](https://citymapper.com/news/1039/the-smartcommute-tm), [rerouting](https://citymapper.com/news/495/route-around-disruptions), [offline](https://citymapper.com/news/1282/offline-support).
- Moovit validates favorites + alerts + crowd evidence as one product loop, but crowd wording still needs a professional synthesis boundary: [features](https://moovit.com/features/).
- GTFS-RT freshness expectations are strict ([best practices](https://gtfs.org/documentation/realtime/realtime-best-practices/)). Malaysia's available vehicle data is therefore reference telemetry, not evidence that a rail disruption exists.
- MapLibre's supported building extrusion and OpenFreeMap's keyless vector styles provide useful spatial depth without decorative 3D assets: [MapLibre 3D](https://maplibre.org/maplibre-gl-js/docs/examples/display-buildings-in-3d/), [OpenFreeMap](https://openfreemap.org/quick_start/).
- Public rider posts are not display content. TrafficMY exposes synthesized incident summaries and source links, never raw text or handles.

---

## 1. Product landscape (by model)

### A. Authority line-status boards (gold standard for glance UX)

| Product | URL / API | Model | What they do well | TrafficMY takeaway |
|---------|-----------|--------|-------------------|-------------------|
| **TfL Line Status** | [tfl.gov.uk](https://tfl.gov.uk/modes/tube/status/) · [API](https://api.tfl.gov.uk/Line/Mode/tube/Status) | Official GTFS + ops | Per-line row, severity 1–20 mapped to Good / Minor / Severe, `reason` text, mode tabs (tube / Overground / DLR) | **Primary UI pattern**: line grid, 4 severity buckets, plain-language reason |
| **SuperNYC Subway** | [supernyc.com/subway](https://supernyc.com/subway) | GTFS-RT → human labels | Good / Delays / Suspended badges, 60s poll, **methodology page**, fails visibly when feed stale | Copy: last-updated timestamp, trust page, no fake “live” |
| **MTA Live Subway Map** | [map.mta.info](https://map.mta.info/) | Real-time map + status | Spatial + line list; color = service state | Optional map layer later; list-first is enough for v1 |
| **National Rail (UK)** | [nationalrail.co.uk/service-disruptions](https://www.nationalrail.co.uk/service-disruptions/) | Multi-operator feed | Operator + route disruption cards, “affecting” copy | Multi-agency Malaysia: RapidKL vs KTMB vs Prasarana labels |
| **Amtrak Status** | [amtrak.com/status](https://www.amtrak.com/status) | Official delays | Train-centric but same severity language | KTM Komuter = same mental model |
| **LTA myTransport (SG)** | [mytransport.sg](https://www.mytransport.sg/) | Gov API + alerts | MRT line colors, planned vs unplanned split | Closest regional peer; separate planned maintenance from crowd reports |
| **HK MTR** | [mtr.com.hk](https://www.mtr.com.hk/en/customer/services/trip_planner_index.html) | Official + push | Line status in trip planner, bilingual | Bilingual MS/EN labels on severity |
| **Sydney Trains** | [transportnsw.info](https://transportnsw.info/travel-info/ways-to-get-around/train/train-disruptions) | Official disruptions | “Major / Minor / Info” + map | Same 3-tier disclosure as Transit.app |

### B. Multi-modal apps (fusion + trip context)

| Product | Model | What they do well | TrafficMY takeaway |
|---------|--------|-------------------|-------------------|
| **[Citymapper](https://ridewithvia.com/resources/how-citymapper-handles-unplanned-disruptions)** | GTFS + RSS + **Twitter/Telegram** + manual ops | “Live ops room” merges feeds; unplanned > planned; human veto on bad social signal | Threads = Twitter layer; official = grounding; never one post = truth |
| **[Moovit](https://en.wikipedia.org/wiki/Moovit)** | Crowd + official + passive GPS | Active “why delayed?” reports; overcrowding as first-class | Future: 1-tap report (out of scope now) |
| **[Transit.app](https://transitapp.com/)** | Agency alerts + UX polish | **Severe / Warning / Info**; actionable copy (“use stop X”); [agency dashboard](https://resources.transitapp.com/article/171-send-alerts-with-the-transit-dashboard) for structured alerts | Severity on line row; drilldown for evidence |
| **Google Maps transit** | Official GTFS-RT + historical | Disruption only when confidence high; integrated in directions | Low-confidence social stays on TrafficMY, not Maps |
| **Apple Maps / HERE** | Partner feeds | Same as Google — conservative official-only | Our niche: **unofficial early signal** |

### C. Crowd / social-signal surfaces (closest to TrafficMY)

| Product | Model | What they do well | TrafficMY takeaway |
|---------|--------|-------------------|-------------------|
| **Down Detector** | Social + search spike | “Something may be wrong” from **volume**, not content understanding | Use cluster volume + multi-source for confidence |
| **Waze** | GPS + user reports | Freshness-first; stale alert worse than none; category pickers (accident / hazard) | Show post age + source; expire old clusters |
| **Google/Waze UX research** | Navigation trust | Users abandon if alerts feel wrong or undated | [Design lessons](https://thecoding.club/designing-better-navigation-ux-lessons-from-a-long-term-goog) |
| **RISECURE (WMATA)** | Twitter + GCN | Station-centric panel, subscriptions, incident **storyline** | Group by line/station timeline; saved lines later |
| **BART Alerts (@SFBART)** | Official social | Short, structured tweets linked to status page | RapidKL @askrapidkl as corroboration target |
| **#TrainDelay UK / @nationalrailenq** | Social + official reply | Community reports until official confirms | “Community report” vs “✓ official” badge |

### D. Enterprise / agency tooling (informs taxonomy, not consumer UI)

| Product | Notes |
|---------|--------|
| **[Translink DMS (AU)](https://vivogroup.com.au/web-design-portfolio/translink-translink-disruption-management-system)** | Disruption type taxonomy, copy templates, multi-channel publish |
| **Swiftly / Optibus** | Agency-side delay management → GTFS-RT |
| **AWS social listening pipelines** | Ingest → classify → route to ops (Citymapper-scale) |

---

## 2. Universal UX principles (web)

Derived from TfL, SuperNYC, Citymapper, Transit, Waze, Down Detector, and transit UX case studies ([MYmta case study](https://uxdesign.cc/chasing-buses-a-ux-case-study-of-mymta-118e7628dcfd)).

1. **Line/status board first** — Users ask “is *my line* OK?” before reading posts. Default view = grid of lines, not raw feed.
2. **Severity taxonomy (max 4–6)** — Normal · Minor · Delay · Disruption (maps to TfL 1–20 and Transit Severe/Warning/Info). Color + text label, never color alone.
3. **Progressive disclosure** — Grid shows status + one-line reason → tap for evidence posts + links → optional map/stations later.
4. **Freshness visible** — “Updated 14:32 MYT · 3 jam lalu”, not vague “live”. Stale data labeled stale ([Waze/Google pattern](https://thecoding.club/designing-better-navigation-ux-lessons-from-a-long-term-goog)).
5. **Trust / methodology** — State sources, limits, and that this is **not** official RapidKL/KTM. Fail visibly when ingest down ([SuperNYC methodology](https://supernyc.com/methodology/subway)).
6. **Corroboration** — One Threads post ≠ confirmed. Badge when official/GTFS agrees ([Citymapper fusion](https://ridewithvia.com/resources/how-citymapper-handles-unplanned-disruptions)).
7. **Actionable when possible** — “Check @askrapidkl” / alternative line ([Transit alert copy](https://resources.transitapp.com/article/171-send-alerts-with-the-transit-dashboard)).
8. **Separate telemetry from incidents** — GPS headway ≠ “fire alarm at station”. Different tab or lower trust (Moovit passive vs active reports).

---

## 3. Information architecture (what the page contains)

Typical high-trust disruption page (TfL, SuperNYC, National Rail):

```
┌─────────────────────────────────────┐
│ Header: brand · last refresh · refresh │
├─────────────────────────────────────┤
│ LINE STATUS BOARD (primary)         │
│  [Badge] Kelana Jaya — Delays…  2h  │
│  [Badge] Kajang MRT — Normal        │
├─────────────────────────────────────┤
│ RECENT REPORTS (secondary feed)     │
│  card → opens evidence drawer       │
├─────────────────────────────────────┤
│ METHODOLOGY / LIMITATIONS (footer)  │
└─────────────────────────────────────┘
```

TrafficMY implements this in `static/index.html` + `GET /api/trafficmy/lines`. The current-status projection expires after 24 hours; the longer 21-day window is evidence history, not live status. Planned projects are separated from operating services.

Detailed Malaysia network, timetable, peak-period, and source research lives in [`MALAYSIA_TRANSPORT_REFERENCE.md`](MALAYSIA_TRANSPORT_REFERENCE.md).

---

## 4. Architecture patterns (industry)

```
Sources (API, scrape, social keyword search)
    → ingest queue (rate-limit, async workers)
    → normalize + classify (severity, line, station, language)
    → quality gate (problem vs mention — NOT every "LRT" post)
    → dedupe / cluster by line+issue
    → line status projection (worst active severity per line)
    → REST API + static dashboard
    → (later) push / saved lines / official priority merge
```

Used at scale by: Citymapper ops, Moovit, TfL open data consumers, AWS Comprehend + social pipelines, RISECURE (Twitter + graph models).

**TrafficMY today:** collect → transform → cluster → **`line_status_service`** → API. Social and GTFS kept separable via `source_group`.

---

## 5. Classification & quality (what others filter)

| Signal | Keep | Drop |
|--------|------|------|
| “Kelana Jaya line delay stuck at Bangsar” | ✓ | |
| “Replying to @x …” thread noise | | ✓ |
| Lifestyle / condo near LRT | | ✓ |
| Telco outage reposted as transport | | ✓ |
| GTFS bus off-route only | Separate GPS tab | Main feed |
| Single old post, no corroboration | Show as Minor + age | Don't mark Disruption |

Citymapper and Moovit both use **human or ML review** for social; TrafficMY uses rules in `transport_incident_signal_ok` until volume justifies ML.

---

## 6. Malaysia-specific reality

| Factor | Implication |
|--------|-------------|
| **Threads > X** for commuter rants | Keyword search primary; X lane dormant without auth |
| **MyRapid / KTMB** | Ground truth when available; scraping fragile |
| **GTFS-RT (bus)** | Telemetry hints, not LRT truth — cap confidence |
| **User mental model** | Lines (Kelana, Kajang, KTM) not cluster slugs |
| **Languages** | MS + EN mixed posts; normalize for matching |
| **No single open API** | Unlike TfL — crowd layer fills gap |

Regional peers: **LTA myTransport (SG)**, **TransJakarta**, **BTS Bangkok** — all authority-first; TrafficMY’s wedge is **early unofficial signal**.

---

## 7. TrafficMY roadmap (research-driven)

| Phase | Feature | Inspired by |
|-------|---------|-------------|
| **Now (shipped)** | Line status board + report timeline + evidence drawer | TfL, SuperNYC |
| **Now (shipped)** | `quality_only` filter, social default, methodology blurb | Citymapper, Waze |
| Next | Dedicated `/methodology` page | SuperNYC |
| Next | Corroboration badge when official RSS matches line | Citymapper |
| Next | Saved lines / browser notify | RISECURE, Transit |
| Later | Station-level drilldown | MTA map, RISECURE |
| Later | User report button | Moovit, Waze |
| **Now (shipped)** | Rail-first GTFS route helper + official mixed-mode fallback | Citymapper, MyRapid |
| **Now (shipped)** | Dated transport updates + pass break-even helper | MyRapid, KTMB |
| Later | Planned vs unplanned split | LTA, National Rail |

---

## 8. What we explicitly do NOT copy

- Turn-by-turn road navigation or a fabricated all-mode planner. TrafficMY stays rail-first and links to MyRapid for official mixed bus + rail planning.
- Login wall for basic status
- Raw keyword feed without quality gate (Down Detector without classification)
- GPS-only as “incident confirmed”
- Pretending to be official RapidKL/KTM

---

## 9. Key references

- TfL API line status: https://api.tfl.gov.uk/Line/Mode/tube/Status  
- SuperNYC methodology: https://supernyc.com/methodology/subway  
- Citymapper unplanned disruptions: https://ridewithvia.com/resources/how-citymapper-handles-unplanned-disruptions  
- Transit agency alerts: https://resources.transitapp.com/article/171-send-alerts-with-the-transit-dashboard  
- RISECURE (WMATA social alerts): https://kaichunf.github.io/papers/zulfiqar2022risecure.pdf  
- MYmta UX case study: https://uxdesign.cc/chasing-buses-a-ux-case-study-of-mymta-118e7628dcfd  
- Navigation UX / freshness: https://thecoding.club/designing-better-navigation-ux-lessons-from-a-long-term-goog  
