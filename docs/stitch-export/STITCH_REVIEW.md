# Stitch MCP review — TrafficMY project

**Project ID:** `15704224234350283213`  
**Pulled:** 2026-07-03 via `@google/stitch-sdk`  
**Screens:** 18 (13 with HTML)

## Verdict: **Yes, it's good — ship this direction**

The Stitch work is strong. It reads as a real Malaysian commuter product, not generic AI slop. The **JomTransit** design system (`DESIGN.md`) is production-grade and already mostly ported to `static/css/stitch.css`.

---

## What's excellent (keep)

| Area | Why it works |
|------|----------------|
| **Neubrutalist tactile UI** | 2px borders + `0 4px 0` solid shadows = pressable, confident, memorable |
| **Nunito Sans 600–900** | Legible on bright platforms / one-handed rush hour |
| **Official line stripes** | Kelana `#E31837`, KTM `#0066B3`, etc. — instant mode recognition |
| **Glance card** | Mascot + “quiet / need attention” sets emotional tone in 2 seconds |
| **Live today signals** | RIDING NOW pill + source tag + time + line stripe = perfect rider-intel card |
| **BM/EN labels** | Home/Utama · Map/Peta · Travel/Gerak — right for audience |
| **Map float card** | Worst active line + Details / Plan — best mobile pattern from `Live Map` screens |
| **Travel passes card** | Orange `#ffdcbf` block separates fares from route planner |
| **420px max width** | Feels native on phone, not stretched desktop |
| **44px touch targets** | Chips, nav, buttons sized for gloves / vibration |

## Best screens to treat as source of truth

| Screen | Stitch title | Use for |
|--------|----------------|---------|
| Home | `TrafficMY - Live Transit Updates` (`8d69c1f5…`) | Glance, Live today, filters, line rows |
| Map | `TrafficMY - Live Map` (`d76f8309…` or `580f1e49…`) | Layer chips, float card, dark map |
| Travel | `TrafficMY - Travel` (`eb82a535…` or `395e93ca…`) | Plan route + passes layout |
| Tokens | `DESIGN.md` / uploaded brief (`15156581818966453464`) | Colors, type scale, elevation rules |

## Nice extras (optional v2)

- **Smart Home Dashboard** — “Rush Hour Survival” stress meter (gamified, fun)
- **Travel Rewards** — commuter streaks / vouchers (engagement layer)
- **Advanced Map Explorer** — station search, mic, crowd layer (heavier map UX)
- **“Alamak!”** glance copy when BM-primary — more local than generic English

## Already merged in live app (v13)

- Stitch header, bottom nav, glance, compact line rows, schematic card
- Signal cards with RIDING NOW + source tags
- Map fullscreen + float card + layer filter sync
- Travel card styling + bilingual section heads

## MCP setup (Cursor)

Workspace config: `.cursor/mcp.json` (gitignored).  
Restart Cursor → Agent can run: *“List my Stitch projects”*, *“Fetch screen HTML for Live Map”*, etc.

Pull latest from Stitch:

```bash
set STITCH_API_KEY=your-key
node scripts/stitch_pull.mjs
```

Output: `docs/stitch-export/mcp-pull/`
