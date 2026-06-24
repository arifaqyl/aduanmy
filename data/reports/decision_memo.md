# AduanMY Decision Memo

Based on the latest verified local ingest.

## Source Reality
- Full ingest loop now completes in about `44.47s` with parallel collectors.
- Threads is the strongest open discovery-style social source in the repo.
- X works as a targeted service-account monitoring lane, not a broad search lane.
- Reddit is usable but still noisier than Threads/X.
- Official pages are grounding rails, not complaint-density rails.

## Current Counts
- stored complaint rows: `13`
- raw source rows:
  - Threads: `5`
  - Reddit: `5`
  - X: `1`
  - Official: `11`

## Current Category Shape
- transport: 8
- telco_internet: 3

## Scorecard
- raw mix: transport | threads | volume=4
- raw mix: transport | reddit | volume=3
- raw mix: telco_internet | reddit | volume=2
- raw mix: telco_internet | official | volume=1
- raw mix: telco_internet | threads | volume=1
- raw mix: transport | official | volume=1
- raw mix: transport | x | volume=1

## Ranked Categories
- `transport`
  - density: `8`
  - source_diversity: `3`
  - verification_potential: `2`
  - demo_value: `2`
  - total: `17`
- `telco_internet`
  - density: `3`
  - source_diversity: `2`
  - verification_potential: `2`
  - demo_value: `2`
  - total: `9`

## Recommendation If Choosing Today
Primary wedge: `TrafficMY`

Why:
- Strongest density, best source diversity, and the cleanest verification/demo story.
- transport and telco are the only categories with a credible verification/demo path right now.
- banking/payments is no longer strong enough after stricter filtering.

## Second Choice
- `ServiceOutageMY` if telco overtakes transport in a later snapshot.

## Not Recommended Yet
- broad `AduanMY` as the shipped product name for v1
- `banking_payments` because the trust story is still weak
- `gov_portals` because the live evidence base is still too thin

## Decision
If a narrower product build started next, build `TrafficMY` first.
