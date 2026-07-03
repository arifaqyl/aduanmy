# Malaysia Public Transport Reference

Verified: 2026-06-28. This is TrafficMY's source-backed network reference and the basis for its rail-first route helper. Operating times and frequencies can change for engineering works, events, Ramadan, public holidays, and operator timetable revisions. The dated operator timetable remains authoritative.

## Product rules derived from the research

1. A disruption status must expire quickly. TrafficMY uses a 24-hour status window; the 21-day window is evidence history only.
2. No recent report means **unknown**, not normal service. Only an operator can confirm normal operations.
3. Planned projects must never appear as live operational lines.
4. Turn-up-and-go Rapid KL frequencies and fixed KTMB timetables are different products. Do not display a generic frequency for KTM.
5. Static route facts are context. Live vehicle telemetry, operator notices, and public incident reports remain separate evidence types.

## Peak periods

Rapid KL defines normal weekday rush hours as **07:00-09:00** and **17:00-19:00**. Its detailed LRT tables commonly use **07:00-09:30** and **17:00-19:30** frequency bands. The product should label these as operator-planned bands, not measured crowding.

Source: [MyRapid FAQ](https://myrapid.com.my/resources/faqs/) and [Rapid KL LRT service information](https://myrapid.com.my/bus-train/rapid-kl/lrt/).

## Operating urban rail

| Service | Operator | Endpoints | Typical service and peak context | Official source |
|---|---|---|---|---|
| LRT Kelana Jaya | Rapid KL | Gombak - Putra Heights | Stations open from 06:00; about 3 min weekday peak | [MyRapid LRT](https://myrapid.com.my/bus-train/rapid-kl/lrt/) |
| LRT Ampang | Rapid KL | Ampang - Sentul Timur | About 6 min on branch, 3 min on shared trunk at peak | [MOT current rail services](https://www.mot.gov.my/en/land/infrastructure/current-rail-services) |
| LRT Sri Petaling | Rapid KL | Putra Heights - Sentul Timur | About 6 min on branch, 3 min on shared trunk at peak | [MOT current rail services](https://www.mot.gov.my/en/land/infrastructure/current-rail-services) |
| MRT Kajang | Rapid KL | Kwasa Damansara - Kajang | 29 stations; about 4 min peak | [MRT Corp Kajang Line](https://www.mymrt.com.my/projects/kajang-line/) |
| MRT Putrajaya | Rapid KL | Kwasa Damansara - Putrajaya Sentral | 36 operating stations; 84 min end-to-end; about 5 min peak | [MRT Corp Putrajaya Line](https://www.mymrt.com.my/projects/putrajaya-line/) |
| KL Monorail | Rapid KL | KL Sentral - Titiwangsa | 11 stations; MyRapid lists about 6 min peak | [MyRapid FAQ](https://myrapid.com.my/resources/faqs/) |
| BRT Sunway | Rapid KL | Sunway-Setia Jaya - USJ 7 | Seven stops; about 6 min peak | [MyRapid BRT](https://myrapid.com.my/bus-train/rapid-kl/brt/) |
| LRT Shah Alam (LRT3) | Rapid KL | Bandar Utama - Johan Setia | Launched 28 June 2026; passenger service starts 06:00 on 29 June; free rides announced for one month | [Launch report](https://www.thestar.com.my/news/nation/2026/06/28/anwar-launches-rm1663bil-lrt3-shah-alam-line) |

Rapid KL broadly operates rail and bus services seven days a week from around 06:00 to midnight. Last-train times vary by station and direction, so TrafficMY links to the operator page rather than storing one false universal closing time.

## KTM and national rail

| Service | Main corridor | Scheduling model | Official source |
|---|---|---|---|
| KTM Komuter Klang Valley | Batu Caves - Pulau Sebang; Tanjung Malim - Port Klang | Dated weekday/weekend timetable | [KTMB train schedule](https://www.ktmb.com.my/traintime.html) |
| KTM Komuter Utara | Padang Besar - Butterworth and Padang Rengas corridors | Dated timetable; frequency changes by period | [KTMB Komuter](https://www.ktmb.com.my/komuter.html) |
| ETS | Gemas - Padang Besar on the electrified West Coast line | Reserved train-specific timetable | [KTMB ETS](https://www.ktmb.com.my/ets.html) |
| KTM Intercity | East Coast and southern corridors, including Shuttle Tebrau | Reserved train-specific timetable | [KTMB maps and routes](https://www.ktmb.com.my/MapsAndRoute.html) |
| Sabah State Railway | Tanjung Aru - Beaufort - Tenom | Limited fixed services; confirm before travel | [JKNS Sabah Railway](https://www.sabahrailway.my/) |

KTMB publishes effective dates for every timetable. The current schedule page includes 2026 revisions for Komuter, Komuter Utara, ETS, Intercity, and southern shuttle services. TrafficMY should link to that page and avoid copying a timetable that becomes stale.

## Airport rail

KLIA Ekspres and KLIA Transit connect KL Sentral with KLIA Terminal 1 and Terminal 2. KLIA Transit also serves Bandar Tasik Selatan, Putrajaya & Cyberjaya, and Salak Tinggi. The current operator page lists a 39-minute KLIA Transit end-to-end journey, roughly 15-minute weekday peak frequency and 30-minute off-peak/weekend frequency. First and last departures vary by direction.

Source: [KLIA Transit timetable](https://www.kliaekspres.com/products-fares/klia-transit/).

## Bus networks

Malaysia does not have one static national bus timetable. TrafficMY should model bus coverage by operator/region and ingest route catalogs dynamically where official GTFS exists.

| Network | Coverage | Useful official facts | Source |
|---|---|---|---|
| Rapid KL Bus | Klang Valley | Stage, feeder and special routes; many routes start around 06:00; last bus and frequency vary | [Rapid KL Bus](https://myrapid.com.my/bus-train/rapid-kl/bus/) |
| Rapid Penang | Penang Island and Seberang Perai | Operator publishes route-level first trip, last trip and frequency | [Rapid Penang routes](https://myrapid.com.my/bus-train/rapid-penang/rapid-pg-bus/) |
| Rapid Kuantan | Kuantan | Route-level service under Rapid Bus | [Rapid Kuantan](https://myrapid.com.my/bus-train/rapid-kuantan/) |
| BAS.MY / contracted stage bus | Selected Malaysian cities | APAD-regulated networks; route details vary by local operator | [APAD](https://www.apad.gov.my/) |

For Rapid KL, MyRapid's general guide says in-town buses commonly target 15-20 minutes during peak periods. This is not a guarantee because road traffic directly affects bus headways.

## Planned and under-construction services

These belong in a clearly labelled future-network section, never in live status.

| Project | Alignment | Current source-backed stage |
|---|---|---|
| ECRL | Kota Bharu through Terengganu and Pahang to Gombak/West Coast connection | Official project site targets passenger operations from January 2027 | [ECRL](https://ecrl.com.my/) |
| RTS Link | Bukit Chagar - Woodlands North | Under construction; cross-border service, with the Malaysian station in Johor Bahru | [MOT new rail projects](https://www.mot.gov.my/en/land/development/new-rail-projects) |
| MRT3 Circle Line | 51 km orbital alignment around Kuala Lumpur | Final railway scheme approved in July 2025; land acquisition targeted through 2026 | [MRT Corp approval](https://www.mymrt.com.my/wp-content/uploads/2025/07/MRTC-MEDIA-RELEASE-MRT3-CIRCLE-LINE-RAILWAY-SCHEME-RECEIVES-FINAL-APPROVAL-Website.pdf) |
| Penang LRT Mutiara Line | PSR-A - Komtar / Penang Sentral branches | Construction underway; revised scheme states operations expected in December 2031 | [MRT Corp Mutiara release](https://www.mymrt.com.my/wp-content/uploads/2026/02/MRTC-FOR-IMMEDIATE-RELEASE-MRT-CORP-ANNOUNCES-PUBLIC-INSPECTION-FOR-LRT-MUTIARA-LINE-EXTENSION-LINKING-ISLAND-AND-SEBERANG-PERAI_1.pdf) |

## Data sources TrafficMY should use

| Need | Best available source | Product treatment |
|---|---|---|
| Rapid KL service status | MyRapid alerts/status surface | Official grounding, timestamp required |
| KTM service status and schedule | KTMB notices and dated timetable page | Official grounding; link rather than copy full timetable |
| Bus position anomalies | Malaysia government/Prasarana GTFS feeds | Telemetry signal, never rail confirmation |
| Network popularity and peak analysis | data.gov.my ridership and hourly origin-destination datasets | Research/analytics, not incident status |
| Early passenger reports | Threads, then Reddit | Unconfirmed public signal with short expiry |
| News of significant incidents | RSS from reputable publishers | Media report, separate from official confirmation |

The [data.gov.my public transport dashboard](https://data.gov.my/dashboard/public-transportation) and [data catalogue](https://data.gov.my/data-catalogue) currently expose nationwide ridership, Rapid Rail origin-destination, BRT, KTMB service, and hourly origin-destination datasets. These are the right inputs for later evidence-based peak/crowding features. They do not provide proof of a current disruption.

## Known gaps

- No single authoritative real-time feed covers all Malaysian rail and bus operators.
- MyRapid pages can be protected by Imperva, so official collection needs visible degradation and cached metadata.
- X public access remains unreliable without authentication.
- Route-level bus schedules are too large and volatile to hand-maintain; use operator pages and GTFS catalogs.
- Planned-project dates conflict across old official pages. TrafficMY should show lifecycle stage and source date, not repeat stale launch promises.

## Research method

Primary-source review across MyRapid/Prasarana, KTMB, MRT Corp, MOT, APAD, data.gov.my, KLIA Ekspres, ECRL, LRT3, and Sabah Railway. Twenty-plus official pages and current 2026 timetable/project materials were compared. Where official pages conflicted, this reference uses cautious lifecycle wording and links to the current operator surface.
