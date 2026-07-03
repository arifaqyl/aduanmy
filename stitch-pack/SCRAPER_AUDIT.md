# Scraper accuracy audit (2026-07-01)

## User complaint

Feed sometimes shows **old posts**, **unrelated topics**, and **news/discussion** — not people **riding right now** with a **current problem**.

## Sources

| Source | Role | Strictness (before fix) |
|--------|------|-------------------------|
| Threads | Primary rider voice | Strict (`transport_rider_signal_worthwhile`) |
| Reddit | Secondary | Loose (`transport_incident_signal_ok` only) |
| RSS / Google News | News headlines | Loose + 21-day window |
| Official | Operator notices | Separate gate |
| X | Optional | Off by default |

## Why bad posts slipped through

1. **Asymmetric gates** — Threads required "stuck / waiting 25 min / fire alarm"; Reddit only needed "delay + train" in a discussion thread.
2. **Wide Reddit search** — `t=year` could surface year-old threads; only 21-day filter applied later.
3. **RSS 21-day window** — News articles about past incidents re-ingested.
4. **`line_info` clusters** — Schedule/trivia surfaced in "recent reports" feed.
5. **Substring line matching** — "ktm" in unrelated text → wrong line.
6. **Timestamp fallback** — Missing `created_at` used `inserted_at` on re-scrape → looked "fresh" when old.
7. **Non-transport on transport category** — e.g. football "delay his run" matched delay keywords.

## Fixes applied (same date)

- Reddit/RSS/X/Threads all pass **`transport_rider_signal_worthwhile`** at ingest
- Reddit search **`t=week`**, RSS/Reddit collector window **3 days** (`RECENT_DAYS`)
- Prune job expanded to **all social platforms** (not Threads-only)
- Line board `recent_reports` filtered with **`_is_real_transport_complaint`**
- Delay posts need **present-tense context** ("again", "today", "stuck") not history essays

## What still needs work

- Station-level line disambiguation (KL Sentral = many lines)
- Reject rows without authoritative timestamps
- UI: show freshness source + "riding now" confidence chip
- Separate **news** watchlist from **rider** watchlist in Threads discovery

## Rider signal definition (code)

A post must have **observable impact while riding**:

- Waiting X minutes, stuck, doors won't open, can't board/exit
- Fire alarm, signal failure, train not moving
- Present tense: today, now, this morning, again (not "in 1998" or "planning to")

File: `app/pipeline/extract.py` → `transport_rider_signal_worthwhile`
