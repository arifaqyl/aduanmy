# Threads Terminal — Full Ops Package

> **Why this exists.**  TrafficMY's public board at [arifaqyl.me/traffic](https://arifaqyl.me/traffic/) is driven almost entirely by real-time rider signals from Meta Threads — complaints, delay reports, crowding notices.  Getting that signal quality right matters: too loose and the board fills with opinion noise; too strict and real disruptions get silenced.  Threads Terminal is the command-line ops console that lets you inspect, debug, and tighten every layer of the Threads scraper pipeline — session health, gate logic, false-positive patterns, and production data — without touching the consumer UI or risking secrets in logs.

**Not** a consumer feature — this is how you debug scraper quality, session health, and false positives.

Live board: https://arifaqyl.me/traffic/

---

## Install

```bash
cd D:\aduanmy
pip install -e ".[dev]"   # includes rich
# or: pip install rich
```

After install you can run the CLI via:

```bash
threads-terminal             # entry-point alias (after pip install -e)
python scripts/threads_terminal.py   # direct, no install needed
python -m scripts.threads_terminal   # module invocation
```

---

## Quick start

```bash
# One-screen dashboard (local DB)
threads-terminal

# Production DB + remote health
threads-terminal dashboard --prod

# Auto-refresh every 30s until Ctrl+C
threads-terminal watch

# One-shot health checklist
threads-terminal doctor

# Interactive menu
threads-terminal interactive --prod

# Local web UI (http://127.0.0.1:8005)
python scripts/threads_terminal_web.py
python scripts/threads_terminal_web.py --prod
```

---

## Commands

| Command | What it does |
|---------|----------------|
| `dashboard [--prod] [--json]` | Session · collector pills · run sparkline · accepted + suspicious samples |
| `watch [--interval N] [--prod]` | Auto-refresh dashboard every N seconds (default 30) until Ctrl+C |
| `doctor [--json]` | One-shot health checklist: session, last run, eval pass rate, gate self-test |
| `session` | Cookie path, age, size, renewal hint |
| `runs` | Recent `collector_runs` for threads |
| `health [--prod]` | Collector health + optional prod `/api/health` |
| `qa [--prod] [--json]` | Re-run gates on recent threads rows |
| `replay "<text>" [--json]` | Step-by-step gates + **matched terms/regexes** |
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

### `--json` flag

`dashboard`, `replay`, `qa`, and `doctor` all accept `--json` — output the raw dict as JSON to stdout (same exit code rules apply).  Useful for scripting:

```bash
threads-terminal dashboard --json | jq '.session.available'
threads-terminal replay "LRT Kelana Jaya delay" --json | jq '.accepted'
threads-terminal doctor --json | jq '.all_ok'
```

### `watch`

```bash
threads-terminal watch               # refresh every 30s
threads-terminal watch --interval 60 # refresh every 60s
threads-terminal watch --prod        # pull from production DB on each cycle
```

Clears the terminal and re-runs `dashboard` on each tick. Press `Ctrl+C` to stop.

### `doctor`

Runs four local checks and exits `0` (all pass) or `1` (any fail):

1. **session.json** — exists, size, age
2. **last run** — most recent `collector_runs` status + row count
3. **eval pass rate** — runs the full `tests/eval/rider_signal_cases.json` harness inline
4. **gate self-test** — 3 hard-coded accept/reject cases that must never regress

```bash
threads-terminal doctor
# exit 0 → all green
# exit 1 → something needs attention

# CI-friendly:
threads-terminal doctor --json | jq -e '.all_ok'
```

---

## Web UI

```bash
python scripts/threads_terminal_web.py           # http://127.0.0.1:8005
python scripts/threads_terminal_web.py --prod    # backend reads prod DB
python scripts/threads_terminal_web.py --port 9000
```

**Keyboard shortcuts in the web UI:**

| Key | Action |
|-----|--------|
| `r` | Focus the Gate Replay textarea |
| `Ctrl+Enter` | Run Gate Replay analysis |

The mode badge (LOCAL / PRODUCTION) reflects the `--prod` flag passed at server startup, or the `?prod=true` URL parameter.

---

## False-positive fix loop (the money path)

```
1. dashboard --prod          → spot bad "Delayed" / suspicious accepted
2. replay "<post>"           → see which gate/term matched
3. case add "..." --reject   → lock regression BEFORE editing gates
4. case run                  → baseline green
5. edit app/pipeline/extract.py
6. case run                  → still green + new case
7. prune --prod --dry-run    → preview cleanup
8. prune --prod              → delete (type yes)
9. python scripts/deploy_do.py
```

Or run the whole loop guided: `threads-terminal guided --prod`

---

## Architecture

```
scripts/threads_terminal.py              # Rich CLI (this file)
scripts/threads_terminal_web.py          # Local FastAPI ops UI (:8005)
app/services/threads_terminal_service.py # All logic (testable, no I/O side effects)
app/pipeline/extract.py                  # Sacred gates — don't loosen without eval cases
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
- `doctor` and `case run` are safe to run in CI — they are read-only and make no network calls

---

## Regression anchors (must stay)

**Reject:** sarcastic `tunggu je la`, future `akan rosak`, generic "delay memang teruk", size/housing opinion blobs.  
**Accept:** measured waits with station + today cue, `tak gerak sekarang`, concrete cause (`signal failure`).

```bash
python -m pytest tests/test_threads_terminal.py tests/test_threads_collector.py -q
python scripts/eval_harness.py
threads-terminal case run
threads-terminal doctor
```
