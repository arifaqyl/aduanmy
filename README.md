# TrafficMY

### Live rider signals for Malaysia transit — today, MYT.

> Not ridership charts. Not an operator all-clear.  
> **What are riders reporting on LRT / MRT / KTM right now?**

[![Live](https://img.shields.io/badge/live-arifaqyl.me%2Ftraffic-1f7a4d?style=flat-square)](https://arifaqyl.me/traffic/)
[![Tests](https://img.shields.io/badge/tests-280%20passing-1f7a4d?style=flat-square)](https://github.com/arifaqyl/aduanmy/actions)
[![License](https://img.shields.io/badge/license-MIT-171c1a?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-2b6a8a?style=flat-square)](pyproject.toml)

**Try it:** [arifaqyl.me/traffic](https://arifaqyl.me/traffic/) · **Ops status:** [/status](https://arifaqyl.me/traffic/status) · **API / embed:** [/developers](https://arifaqyl.me/traffic/developers)

---

## Why this exists

Malaysia’s rail apps tell you the timetable.  
They don’t tell you *“Bangsar is stuck for 25 minutes right now.”*

TrafficMY watches rider posts (Threads + Reddit + RSS), runs them through **strict gates**, and publishes a clean line board:

| Quiet | Delayed | Disruption |
|-------|---------|------------|
| No qualifying rider signal today | Live wait / delay reports | Strong multi-signal incident |

**Quiet ≠ all-clear.** Absence of signal is not proof trains are fine.

---

## Demo — Threads Terminal (ops console)

The scraper is the product. **Threads Terminal** is how you keep it honest:

```bash
python scripts/threads_terminal.py replay "Kelana Jaya Line delay again, waiting 25 minutes at Bangsar station hari ni"
```

```
ACCEPTED  entity=Kelana Jaya Line  location=Bangsar
  PASS  non_live_opinion
  PASS  transport_incident_signal_ok     matched: delay
  PASS  malaysia_transport_anchor        matched: Kelana Jaya Line, Bangsar
  PASS  today_context                    matched: hari ni
  PASS  rider_signal_worthwhile          matched: waiting, hari ni
```

Opinion / sarcasm / “akan rosak nanti” threads get **rejected** — not shown as Delayed:

```bash
python scripts/threads_terminal.py replay "ko tunggu je la dia akan ada problem cepat rosak"
# → REJECTED  non_live_opinion  matched: TRANSPORT_SARCASTIC_WAIT_RE, …
```

Full ops pack: [docs/THREADS_TERMINAL.md](docs/THREADS_TERMINAL.md)

```bash
python scripts/threads_terminal.py dashboard --prod
python scripts/threads_terminal.py guided --prod
python scripts/threads_terminal_web.py          # local UI :8005
```

---

## What’s shipping

- **Live board** — Klang Valley LRT/MRT/Monorail/KTM + planned lines
- **Map** — MapLibre pins snapped to rail geometry
- **Travel** — station planner, headways, passes
- **Trust copy** — bilingual EN/BM · quiet ≠ all-clear
- **Signals API** — `GET /api/trafficmy/signals/today` for embeds / B2B
- **Eval harness** — labelled false-positive set; don’t loosen gates without cases

Engine name: **AduanMY**. Product surface: **TrafficMY**.

---

## Trust boundary (non-negotiable)

1. A rider post is an **early signal**, never automatic truth  
2. Raw @handles / full posts stay **internal** — public output is synthesized  
3. Official operator channels remain the final travel check  
4. GTFS is reference only — never “confirms” an incident  
5. Gates reject politics, housing, grab-waits, planning debates, future speculation

---

## Quick start

```bash
git clone https://github.com/arifaqyl/aduanmy.git
cd aduanmy
pip install -e ".[dev]"
python -m pytest tests -q
uvicorn app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/

Docker:

```bash
docker compose up --build -d
# → http://localhost:8002/
```

---

## Architecture (one glance)

```
Threads / Reddit / RSS / Official
            │
            ▼
   extract.py gates  ──►  reject noise (eval-backed)
            │
            ▼
   cluster + corroborate  ──►  professional public summary
            │
            ▼
   TrafficMY PWA  ·  Signals API  ·  Threads Terminal
```

| Source | Role |
|--------|------|
| **Threads** | Primary rider-signal lane |
| Reddit | Secondary (cadenced) |
| RSS | Malaysian transport headlines |
| Official (MyRapid / KTMB) | Grounding only |
| GTFS static | Map / journey reference |

---

## Star if you care about…

- Open, **honest** transit intelligence for SEA cities  
- Scrapers that **refuse** to lie (quiet ≠ fine)  
- Ops tooling that makes false positives fixable in one guided loop  

Issues and PRs welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).  
Security: [SECURITY.md](SECURITY.md).

---

## Author

**Arif Aqyl** — building live products from Malaysia  

[arifaqyl.me](https://arifaqyl.me) · [X @mindofaqyl](https://x.com/mindofaqyl) · [LinkedIn](https://linkedin.com/in/arifaqyl) · hello@arifaqyl.me

## License

[MIT](LICENSE)
