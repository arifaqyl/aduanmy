# Source Capability Matrix

Verified against the current repo plus live public fetches on 2026-06-22.

| Source | Current Primary Path | Verified Now | Strength | Weakness | Recommended Next Step |
|---|---|---|---|---|---|
| Threads | public post fetch + Playwright public profile discovery | yes | best current social signal quality | profile discovery still returns a lot of non-complaint chatter | keep exact post seeds, add smarter complaint/entity filtering, consider a stronger public search lane |
| Reddit | `old.reddit.com` HTML search | yes | good complaint text depth, easy URL traceability | noisy relevance, `.json` route blocked with `403` | keep HTML route, tighten category/entity gates, consider OAuth only if scale matters |
| X | Playwright public profile timeline + direct status-page fetch | yes, for targeted accounts | real incident/support/update posts from public service accounts | search remains weak and public discovery is still narrow | keep targeted profile scraping now, add session-backed search later |
| Official / open data | direct public pages | yes | stable grounding and verification | low complaint density | keep as verification rail, not as the main social source |

## Hard Findings

- Threads is the most promising social lane in the repo right now.
- Reddit is viable, but still the noisiest source by far.
- X is now useful for targeted public service-account monitoring, but still not broad enough for open discovery.
- Official/open-data sources help confidence and cross-checking, but they will not produce the wedge by themselves.

## Practical Source Ranking

1. Threads
2. Reddit
3. Official / open data
4. X for broad discovery

## External Tooling Notes

- A public Playwright-style Threads scraper is the right pattern for this project.
- The suggested `Zeeshanahmad4/Threads-Scraper` repo was cloned and inspected locally, but the checkout is incomplete as published: `src/main.py` imports `scraper.threads_scraper`, and that file is missing.
- Because of that, the repo is useful as a directional reference, not as a drop-in dependency.
- AduanMY now uses the same practical idea directly: real browser render for public profile discovery, then exact post fetches for structured text extraction.
