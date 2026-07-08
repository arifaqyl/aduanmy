# Threads Terminal — Full Ops Package

Ops console for TrafficMY’s **primary rider-signal lane** (Meta Threads).  
**Not** a consumer feature — this is how you debug scraper quality, session health, and false positives.

Live board: https://arifaqyl.me/traffic/

---

## Install

```bash
cd D:\aduanmy
pip install -e ".[dev]"   # includes rich
# or: pip install rich
```

---

## Quick start

```bash
# One-screen dashboard (local DB)
python scripts/threads_terminal.py

# Production DB + remote health
python scripts/threads_terminal.py dashboard --prod

# Interactive menu
python scripts/threads_terminal.py interactive --prod

# Local web UI (http://127.0.0.1:8005)
python scripts/threads_terminal_web.py
python scripts/threads_terminal_web.py --prod
```

---

## Commands

| Command | What it does |
|---------|----------------|
| `dashboard [--prod]` | Session, collector, recent runs, accepted + suspicious samples |
| `session` | Cookie path, age, size, renewal hint |
| `runs` | Recent `collector_runs` for threads |
| `health [--prod]` | Collector health + optional prod `/api/health` |
| `qa [--prod]` | Re-run gates on recent threads rows |
| `replay "<text>"` | Step-by-step gates + **matched terms/regexes** |
| `rejects [--prod]` | Reject-reason histogram |
| `collect [--write]` | Live Playwright sample (+ optional JSON dump) |
| `case add "<text>" --reject\|--accept [--note]` | Append labelled eval case |
| `case run` | Run eval harness (precision/recall) |
| `impact [--prod]` | Per-entity severity if failing rows were pruned |
| `prune --prod [--dry-run]` | Preview / delete rows failing current gates |
| `export [--prod]` | Write `output/threads_terminal_report.json` |
| `guided [--prod]` | Interactive QA → replay → case → eval → prune |
| `interactive [--prod]` | Numbered menu |

Exit codes: `0` healthy / success · `1` degraded or failures (scriptable).

---

## False-positive fix loop (the money path)

```
1. dashboard --prod          → spot bad “Delayed” / suspicious accepted
2. replay "<post>"           → see which gate/term matched
3. case add "..." --reject   → lock regression BEFORE editing gates
4. case run                  → baseline green
5. edit app/pipeline/extract.py
6. case run                  → still green + new case
7. prune --prod --dry-run    → preview cleanup
8. prune --prod              → delete (type yes)
9. python scripts/deploy_do.py
```

Or: `python scripts/threads_terminal.py guided --prod`

---

## Architecture

```
scripts/threads_terminal.py              # Rich CLI
scripts/threads_terminal_web.py          # Local FastAPI ops UI (:8005)
app/services/threads_terminal_service.py # All logic (testable)
app/pipeline/extract.py                  # Sacred gates — don’t loosen without eval cases
app/collectors/threads/{client,session}.py
tests/test_threads_terminal.py
tests/eval/rider_signal_cases.json
scripts/eval_harness.py
scripts/prune_prod_rejected.py
docs/THREADS_TERMINAL.md                 # this file
```

---

## Trust rules

- Quiet ≠ all-clear on the public board
- Never publish raw @handles / full Threads text on the consumer site
- Terminal may show truncated previews for debugging
- Do **not** loosen `transport_rider_signal_worthwhile()` without a labelled eval case first
- All prod DB / prune actions require explicit `--prod`

---

## Regression anchors (must stay)

**Reject:** sarcastic `tunggu je la`, future `akan rosak`, generic “delay memang teruk”, size/housing opinion blobs.  
**Accept:** measured waits with station + today cue, `tak gerak sekarang`, concrete cause (`signal failure`).

```bash
python -m pytest tests/test_threads_terminal.py tests/test_threads_collector.py -q
python scripts/eval_harness.py
python scripts/threads_terminal.py case run
```
