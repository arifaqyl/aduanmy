# Launch kit — TrafficMY on X

Copy, paste, ship. Goal: stars + forks from builders who care about honest transit data.

---

## Pre-flight (do these first)

1. **Push `main`** with README + Threads Terminal + tests green (`270+`)
2. Hard-refresh live: https://arifaqyl.me/traffic/ — Departure Board theme, Quiet lines correct
3. Pin repo topics on GitHub: `malaysia` `transit` `lrt` `mrt` `open-source` `fastapi` `pwa` `threads`
4. Optional: add a 15s screen recording of Home → Map → Line tap → Terminal replay (attach to tweet 1)

---

## Tweet thread (EN)

**1/ hook**
```
I built TrafficMY — live rider signals for Malaysia LRT/MRT/KTM.

Not ridership charts.
Not “all trains normal.”

Just: what are riders reporting TODAY (MYT)?

Quiet ≠ all-clear.

→ https://arifaqyl.me/traffic/
→ https://github.com/arifaqyl/aduanmy
```

**2/ the hard part**
```
The hard part isn’t the UI.

It’s refusing to lie.

Opinion threads (“3-car LRT3 will break later”) used to show as Delayed.

Now the gate rejects sarcasm, future speculation, and scrape chrome — across EVERY line, not one-off phrase lists.

Ops console: Threads Terminal (in the repo).
```

**3/ demo**
```
python scripts/threads_terminal.py replay "Kelana Jaya delay 25 min at Bangsar hari ni"
→ ACCEPTED

python scripts/threads_terminal.py replay "ko tunggu je la dia akan rosak nanti"
→ REJECTED (non_live_opinion)

False-positive fix loop is one command: guided --prod
```

**4/ ask**
```
If you ride RapidKL / KTM — try the board and roast the false positives.

If you build scrapers / city data — star the repo and open an issue with a bad post we should reject.

MIT · 270 tests · Malaysia-first.

https://github.com/arifaqyl/aduanmy
```

---

## Tweet thread (BM — optional quote / reply)

```
TrafficMY — isyarat penumpang langsung untuk LRT/MRT/KTM.

Senyap ≠ semua okay.
Bukan carta ridership.
Bukan laman rasmi RapidKL.

Cuba: https://arifaqyl.me/traffic/
Kod: https://github.com/arifaqyl/aduanmy
```

---

## Who to tag / reply (don’t spam)

- Malaysian builder / open-source accounts you already talk to
- Transit / urbanist accounts *only* if the product is useful to them
- Reply to your own thread with a screenshot of the board + Terminal reject

Avoid: tagging RapidKL / Prasarana as if this is official.

---

## Pin on GitHub

Repo description:
```
TrafficMY — live Malaysia transit rider signals (today MYT). Quiet ≠ all-clear. FastAPI + PWA + Threads Terminal.
```

Website: `https://arifaqyl.me/traffic/`

---

## After it hits

- Reply to every technical question in-thread for 24h
- Turn good false-positive reports into `case add --reject` + PR
- Don’t oversell GPS train positions or “official status”
