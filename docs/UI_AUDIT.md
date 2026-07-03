# TrafficMY — UI audit (Jun 2026)

Benchmarks: [TfL Line Status](https://tfl.gov.uk/modes/tube/status/), [SuperNYC Subway](https://supernyc.com/subway), Citymapper disruption UX. Research: [PRODUCT_RESEARCH.md](PRODUCT_RESEARCH.md). Taste rules: [TASTE.md](TASTE.md).

---

## What was already good (pre-brand pass)

| Area | Assessment |
|------|------------|
| Information architecture | Line board first, reports secondary, methodology collapsed — matches TfL/SuperNYC IA |
| Severity taxonomy | Four buckets with text labels, not color alone |
| Progressive disclosure | Row → drawer with evidence posts |
| API integration | Subpath-aware `APP_BASE`, refresh countdown, stale dot |
| Malaysia scope | Line names, MS copy, MYT timestamps |
| Mobile | Sticky header, horizontal filter scroll, drawer full-width |

---

## AI-slop tells found (pre-fix)

| Tell | Source violated | Was |
|------|-----------------|-----|
| Inter + slate-900 + sky cyan | taste-skill §0.D, §4.1 | `#06080d`, `#38bdf8`, Inter 400–800 |
| Decorative radial gradients | taste-skill LILA, tastesmd REJECT | `body::before` cyan/indigo glow |
| Pulsing glow on live dot | tastesmd motion restraint | `box-shadow: 0 0 8px` + infinite pulse |
| Emoji empty states | taste-skill §3.D | 🚉 📡 in empty blocks |
| Text-only logo | brand gap | `Traffic<span>MY</span>` with accent span |
| Glassy sticky header | taste-skill §4 (dashboards) | Heavy `backdrop-filter` + blur |

---

## Shipped in this pass

| Change | Anti-slop source |
|--------|------------------|
| IBM Plex Sans + Mono + Barlow Condensed (brand only) | taste-skill §4.1, anthropics frontend-design |
| Warm stone palette, burnt-orange `#c2410c` accent | taste-skill §4.2, anthropics (avoid default dark+cyan) |
| Removed `body::before` gradient mesh | tastesmd REJECT gradients-as-decoration |
| Static live dot (no glow pulse) | tastesmd thresholds, taste-skill MOTION 2 |
| `logo.svg` + `favicon.svg` rail-junction mark | User brand brief |
| Text empty states (no emoji) | taste-skill §3.D |
| Header uses logo image + calmer border (less glass) | frontend-design-direction |
| OG + theme-color meta aligned to palette | Brand consistency |

---

## Still weak (honest)

| Gap | Benchmark | Priority |
|-----|-----------|----------|
| No dedicated `/methodology` page | SuperNYC | Medium |
| No official corroboration badge wired to RSS | Citymapper | Medium |
| No saved lines / push | Transit, RISECURE | Later |
| No station-level drilldown | MTA map | Later |
| Single HTML file — no design-system package | Carbon/Fluent for dense dashboards | Acceptable for v1 |
| Logo is SVG text+geometry, not print-ready brand kit | Full identity | Low |

---

## Quality assessment (one paragraph)

TrafficMY’s **structure** was already at TfL/SuperNYC tier before this pass; the weakness was **visual defaults** (Inter, cyan glow, gradient mesh) that read as generic AI dashboard. After applying [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill), [anthropics/frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design), and [tastesmd/TASTES.md](https://github.com/tastesmd/TASTES.md) constraints, the UI is a restrained, scannable status board with a distinct rail-mark brand and warm neutral palette. It is not yet a full design-system product like TfL’s live site, but it no longer looks like a template dark-mode SaaS clone.
