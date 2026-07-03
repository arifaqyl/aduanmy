# TrafficMY — Stitch redesign brief

Upload **this file** + **`trafficmy-ui.html`** to Stitch (HTML and MD only — no zip).

**Live app:** https://arifaqyl.me/traffic/  
**Audience:** Malaysian commuters on phone, one hand, rush hour, BM + EN

---

## Product goal

Answer in under 5 seconds: **Is my line delayed right now?** · **How fresh is this?** · **Rider report or official?**

Not generic AI dashboard slop. Think **Duolingo clarity** + **Citymapper density** + **Malaysia honesty**.

---

## 3 tabs (bottom nav)

| Tab | Purpose |
|-----|---------|
| **Home** | Glance → Live today → search/filters → line board |
| **Map** | Dark map, layer chips, rider pins, line colours |
| **Travel** | Plan route, passes, deals |

---

## Home screen hierarchy (top → bottom)

1. **Glance card** — mascot + "2 lines need attention" or "Looking quiet"
2. **Live today** — horizontal cards: rider signal, source (Threads), time, **Riding now** badge
3. **Search** + sort (Severity / Freshest)
4. **Filter chips** — All · Saved · Rail · LRT · MRT · KTM · Mono · Bus
5. **Line board** — each row: colour stripe, line name, status pill, short reason

---

## Map screen

- Chips: Reports · LRT · MRT · Monorail · KTM · Changes · Bus GPS
- **One network at a time** when user taps LRT (not all layers on)
- Pin colours: red/orange/yellow = reports · blue = KTM train GPS · orange = bus GPS
- Sidebar: lines matching active filter

---

## Travel screen

- From / To station inputs, swap button, Plan route
- Passes section (My50 note)
- Deals strip (optional)

---

## Official line colours (do not change)

| Line | Hex |
|------|-----|
| Kelana Jaya LRT | `#e31837` |
| Ampang / Sri Petaling | `#f7941d` |
| Kajang MRT | `#007a33` |
| Putrajaya MRT | `#f4c300` |
| Monorail | `#8dc63f` |
| KTM Komuter | `#0066b3` |

---

## Status semantics

| Status | Meaning |
|--------|---------|
| Unknown / quiet | No rider signal **today** — NOT "all clear" |
| Minor | Small complaint cluster |
| Delay | Multiple reports or strong signal |
| Disruption | Fire, suspension, major |
| Ended for today | After last train (MYT) |

---

## Redesign must fix

1. **One clear hierarchy** per tab — not scattered blocks
2. **Official vs crowd** visible on every signal (badge or icon)
3. **Time + source** on every card ("12m ago · Threads")
4. **Riding now** badge when someone reports stuck / waiting / doors / fire alarm
5. Map: don't confuse KTM blue with bus orange GPS
6. BM/EN toggle — short labels that fit chips

---

## Design direction options

**A — Playful commuter (current)**  
Nunito, green `#58CC02`, chunky buttons, train mascots, soft cards

**B — Departure board**  
IBM Plex Mono, dark `#121212`, flip-dot feel, max data density

Pick one direction and commit — don't blend both.

---

## Copy tone

- Honest: "No signal today" not "All good!"
- Malaysia: My50, tap-out, interchange names, rush hour MYT
- Short BM/EN pairs

---

## Reference file

`trafficmy-ui.html` — static mockup of all 3 tabs with sample data and inline styles. Redesign this layout; it is structure + content reference, not final polish.
