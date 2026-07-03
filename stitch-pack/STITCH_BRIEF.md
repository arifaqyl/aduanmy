# TrafficMY — Stitch redesign brief

**Product:** Malaysia commuter transport status (LRT, MRT, Monorail, KTM, Rapid bus)  
**Live URL:** https://arifaqyl.me/traffic/  
**Audience:** People on the train/bus *right now* — phone, one hand, rush hour, BM + EN

---

## What to redesign

Mobile-first PWA. **Not** generic AI dashboard slop. Think: Duolingo clarity + Citymapper density + Malaysia-specific honesty.

### 3 tabs (bottom nav)

| Tab | Purpose |
|-----|---------|
| **Home** | Glance card → Live today feed → search → line board (severity per line) |
| **Map** | MapLibre dark map, layer chips (LRT/MRT/KTM…), rider pins, line geometry |
| **Travel** | Journey planner, passes, deals |

### Home layout (current)

- Sticky search + filter chips: All · Saved · Rail · LRT · MRT · KTM · Mono · Bus
- **Klang Valley schematic** (SVG) — tap line to scroll board
- Line rows: colour stripe, name, status badge, mascot tone
- **Live today** — horizontal scroll of freshest rider signals

### Map layout

- Toolbar chips sync with Home filter (LRT only = LRT lines only)
- Sidebar: active lines list
- Pins: orange/yellow/red = rider reports; blue = KTM GPS; orange = bus GPS

### Design constraints

- **WCAG AA** contrast, **44px** min touch targets
- **BM/EN toggle** — labels must fit both languages
- Line colours are **official** (do not recolour):
  - Kelana Jaya LRT `#e31837`
  - Ampang/Sri Petaling `#f7941d`
  - Kajang MRT `#007a33`
  - Putrajaya MRT `#f4c300`
  - Monorail `#8dc63f`
  - KTM `#0066b3`
- Status semantics: `unknown` ≠ all-clear; quiet means no recent rider signal
- Service ends at last train (MYT) — show "Ended for today"

### What riders hate (fix in redesign)

1. Information scattered — one clear hierarchy per tab
2. Can't tell official vs crowd report at a glance
3. Map layers confusing (blue KTM vs bus GPS)
4. Feed shows **old or unrelated** posts (see SCRAPER_AUDIT.md) — UI should show **time + source + "riding now?"** confidence

### Suggested redesign directions

- **Playful commuter** (current: Nunito, green, mascots) — refine, don't flatten
- Or **departure board** (IBM Plex Mono, high contrast) — see `DESIGN.md` in repo
- Show **"last seen · Threads/Reddit"** on every signal card
- **Riding now** badge when post has live context (stuck, waiting X min, fire alarm, etc.)

---

## Files in this zip

```
index.html          — full page structure (3 tabs, panels, forms)
static/css/play.css — current Play theme (primary stylesheet)
static/lines/kv-system.svg — Klang Valley schematic
static/mascots/*.svg — train mascots by mood
static/logo.svg
SCRAPER_AUDIT.md    — why feed accuracy is hard today
```

**Not included:** `app.js` (logic), backend, database — visual reference only.

---

## Copy tone

- Honest, not alarmist: "No signal today" not "All good!"
- Malaysia-specific: My50, tap-out, rush hour MYT, interchange names
- Short BM/EN pairs, not machine-translated walls of text
