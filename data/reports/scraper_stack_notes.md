# Scraper Stack Notes

Updated: 2026-06-22

## Current external references

- `Zeeshanahmad4/Threads-Scraper`
  - GitHub: `https://github.com/Zeeshanahmad4/Threads-Scraper`
  - Current public repo positioning: public Threads scraping, no-login operation, dynamic rendering support, structured output.
  - Why it matters here: it validates the same broad pattern AduanMY is already using for Threads, which is browser-assisted public discovery followed by structured extraction.
  - Why it is not a direct dependency here: the local checkout we inspected was incomplete, so it is safer as a reference pattern than as imported code.

- `vladkens/twscrape`
  - GitHub: `https://github.com/vladkens/twscrape`
  - Current repo posture: X scraping with authorized accounts, cookie-based setup, better for search and broader coverage than anonymous scraping.
  - Why it matters here: it is the clearest next-step upgrade path if AduanMY needs wider X discovery than targeted public service-account monitoring.
  - Why it is not in phase 1 yet: phase 1 is proving public-source viability first, and the current repo already has a narrower public X lane working.

- `fbsamples/threads_api`
  - GitHub: `https://github.com/fbsamples/threads_api`
  - Current posture: official sample app for authenticated Threads API integrations.
  - Why it matters here: it is a credible future path for official integrations or account-owned data, but it does not solve the current public complaint discovery problem by itself.

- Reddit `.json` scraping discussions
  - Example references:
    - `https://www.reddit.com/r/webscraping/comments/1u15pa6/getting_403_while_scraping_reddit_with_json/`
    - `https://www.reddit.com/r/redditdev/comments/1txd5mm/reddit_json_endpoints_returning_403/`
  - Why they matter here: they support what the repo already verified locally, which is that unauthenticated Reddit `.json` access is brittle now and should not be the primary lane.

## What these references changed in AduanMY

- Threads stays the strongest public discovery source in phase 1.
- X stays in the repo, but as targeted profile monitoring first, not broad anonymous search.
- Reddit stays on the `old.reddit.com` HTML lane instead of pretending the `.json` route is dependable.
- Public repo ideas are reused as patterns, not copied in blind.

## Practical stack decision

If phase 1 continues without adding account-backed auth:

1. Keep Threads on the current public Playwright-assisted lane.
2. Keep X on targeted public service-account monitoring.
3. Keep Reddit on HTML search with stricter filtering.
4. Use official/open-data pages only for grounding and cross-checking.

If phase 2 needs broader X discovery:

1. Add a session-backed `twscrape` lane behind a feature flag.
2. Keep the current public X collector as the no-credential fallback.
