# First Findings

Generated from the latest verified ingest run on 2026-06-22.

## What is actually working

- Threads:
  - exact complaint post URLs work well
  - public profile discovery via Playwright works
  - only a small share of discovered profile posts survive complaint filtering, which is expected
- Reddit:
  - `old.reddit.com` HTML search works
  - text depth is better than X
  - complaint precision is still uneven
- Official:
  - strong as a grounding rail
  - weak as a discovery rail

## What is not strong enough yet

- X:
  - targeted public service-account scraping now works
  - broad discovery and search still do not
- Reddit precision:
  - some posts still get dragged into banking or gov buckets because the query lane is broad

## Current category shape

- `transport` is strongest right now
- `telco_internet` is second and credible
- `gov_portals` exists but is still shallow
- `banking_payments` has volume, but the verification story is weaker because it is mostly Reddit-only

## Current interpretation

If a product had to be chosen today, the top wedges would be:

1. `TrafficMY`
2. `ServiceOutageMY`
3. `PortalWatchMY`

## Why

- telco and transport both have:
  - public complaint language
  - recognizable named entities
  - official/provider grounding paths
  - clear demo value
- gov portals are interesting, but the signal is thinner today
- banking is tempting, but the current evidence is not clean enough yet
