# TrafficMY — TASTE (sourced anti-slop rules)

TrafficMY applies external anti-AI-slop guidelines. This file **cites sources** and maps them to this product. Do not treat this as a bespoke style guide invented in isolation.

---

## Source repos & skills (authoritative)

| Source | URL | Role |
|--------|-----|------|
| **Leonxlnx/taste-skill** (`design-taste-frontend`) | https://github.com/Leonxlnx/taste-skill | Anti-slop frontend skill: brief inference, three dials, LILA rule, Inter ban, pre-flight |
| **anthropics/skills** (`frontend-design`) | https://github.com/anthropics/skills/tree/main/skills/frontend-design | Distinctive UI: subject-grounded palette/type, avoid AI default clusters |
| **tastesmd/TASTES.md** | https://github.com/tastesmd/TASTES.md | REJECT / REQUIRE / WHEN AMBIGUOUS format for executable taste |
| **ECC frontend-design-direction** (local) | `C:\Users\askkr\.agents\skills\frontend-design-direction\SKILL.md` | Product UI: scannable tools, no purple blobs, no cards-in-cards |

Install taste-skill: `npx skills add https://github.com/Leonxlnx/taste-skill --skill design-taste-frontend`

---

## Design read (taste-skill §0)

**Reading this as:** trust-first public-transit status board for Malaysian commuters, with TfL / SuperNYC utilitarian language, leaning toward dense data UI (not marketing landing).

**Dials:** `DESIGN_VARIANCE: 3` · `MOTION_INTENSITY: 2` · `VISUAL_DENSITY: 5` (public-sector / status-board preset, taste-skill §1.A)

---

## REJECT (distilled from sources)

- Never use `Inter` as default UI font ([taste-skill §4.1](https://github.com/Leonxlnx/taste-skill), [anthropics frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design)).
- Never use cyan-on-near-black + radial mesh gradients as decoration ([taste-skill §0.D LILA rule](https://github.com/Leonxlnx/taste-skill), [tastes.md](https://tastes.md)).
- Never use purple/indigo accent glows on chips, dots, or CTAs ([frontend-design-direction](C:\Users\askkr\.agents\skills\frontend-design-direction\SKILL.md)).
- Never use emoji as empty-state icons ([taste-skill §3.D](https://github.com/Leonxlnx/taste-skill)).
- Never use pulsing glow `box-shadow` on live indicators ([tastesmd: decorative motion](https://github.com/tastesmd/TASTES.md)).
- Never use route line colors as page chrome — they are functional only ([TrafficMY scope](PRODUCT_RESEARCH.md)).
- Never pretend to be official RapidKL/KTM ([PRODUCT_RESEARCH.md](PRODUCT_RESEARCH.md)).

---

## REQUIRE (distilled from sources)

- Use **IBM Plex Sans** body + **IBM Plex Mono** for timestamps/countdown ([taste-skill §4.1 IBM/Carbon pairing](https://github.com/Leonxlnx/taste-skill)).
- Use **Barlow Condensed** for brand wordmark only — one display face, restrained ([anthropics: type carries personality](https://github.com/anthropics/skills/tree/main/skills/frontend-design)).
- Use warm stone neutrals: `#111318` bg, `#ece8e1` text, `#c2410c` single brand accent ([taste-skill §4.2](https://github.com/Leonxlnx/taste-skill)).
- Maintain line-status board as first viewport — no hero marketing ([frontend-design-direction](C:\Users\askkr\.agents\skills\frontend-design-direction\SKILL.md), [PRODUCT_RESEARCH.md](PRODUCT_RESEARCH.md)).
- Ensure severity = color **and** text label ([PRODUCT_RESEARCH.md §2](PRODUCT_RESEARCH.md)).
- Show freshness timestamp MYT; label stale data ([SuperNYC pattern](PRODUCT_RESEARCH.md)).
- Use `static/logo.svg` in header, favicon, footer ([brand asset rule]).
- Keep transitions ≤ `200ms`, `cubic-bezier(0.2, 0.8, 0.2, 1)` ([tastes.md thresholds](https://tastes.md)).

---

## WHEN AMBIGUOUS

- Subtract rather than add ([tastesmd](https://github.com/tastesmd/TASTES.md)).
- Orient toward: **TfL line status** (clarity), **SuperNYC** (honest methodology), **GOV.UK** (trust-first density).
- Malaysian context via copy and real line names — not flag kitsch or batik textures.
- If taste conflicts with scan speed, **scan speed wins**.

---

## Logo usage

| Asset | Path | Use |
|-------|------|-----|
| Wordmark + rail mark | `static/logo.svg` | Header, OG image reference |
| Favicon | `static/favicon.svg` | Browser tab |

Mark = parallel rails + junction (transit infrastructure). Not globe, not map pin, not generic “location” icon.

---

## UI audit

See [UI_AUDIT.md](UI_AUDIT.md) for benchmark comparison and shipped changes.

---

## TrafficMY slop audit 2026-06-28

Audit against [taste-skill](https://github.com/Leonxlnx/taste-skill), [anthropics frontend-design](https://github.com/anthropics/skills/tree/main/skills/frontend-design), [TASTES.md](https://github.com/tastesmd/TASTES.md), and local frontend-design-direction.

### Violations found and fixed

| Issue | Where | Fix |
|-------|-------|-----|
| Marketing hero block above board | `index.html` `.hero` | Removed visible hero; board is first viewport. Scope note moved to sr-only intro. |
| Decorative map hero SVG | Map tab `#mapHeroSvg` | Removed redundant schematic; map uses GTFS layer only. |
| Glassmorphism drawer backdrop | `#backdrop` `backdrop-filter: blur` | Replaced with solid `rgba(0,0,0,.72)` overlay. |
| Decorative card gradients | `.tool-card`, `.update-card.featured` | Flat `var(--surface)` backgrounds; accent via border only. |
| Pulsing edge / glow animations | `.severity-pulse`, `.markerGlow`, `.schemPulse`, `.rowEnter`, `mapFadeIn` | Removed decorative motion; disruption rows use static left stripe only. |
| Drop-shadow glow on schematic | `updateSchematic()` JS | Opacity highlight only, no filter glow. |
| Journey step halo glow | `.step-mark` box-shadow | Simple bordered dot. |
| `system-ui` font fallback | `index.html`, `methodology.html`, `logo.svg` | IBM Plex + Barlow Condensed only; `sans-serif` ultimate fallback. |
| Unicode icon buttons (★ ↗ ✓) | Line rows, board summary, panel close | Replaced with text labels: Pin, Share, Official, OK/Alert, Close. |
| Startup-style tool headings | Plan tab uppercase 23px title | Sentence-case 16px utilitarian heading. |
| Orange focus ring off-brand | Form focus `#fb923c` | Burnt-orange accent `rgba(194,65,12,.45)`. |
| Map zoom showing foreign tiles | Leaflet `minZoom: 6` | Raised to `minZoom: 8`, `worldCopyJump: false`, Malaysia `maxBounds`. |
| Corrupted SVG metadata | `lrt3.svg` | Fixed middle-dot encoding in station count line. |
| Unicode icon buttons in methodology | `methodology.html` | Replaced checkmark with text label Official. |
| Journey swap glyph | Plan tab swap control | Text label Swap instead of decorative symbol. |
| Panel close icon-only | `#closePanel` | Text Close with utilitarian button sizing. |

### Confirmed compliant (no change)

- IBM Plex Sans body, IBM Plex Mono timestamps, Barlow Condensed brand
- Warm stone palette `#111318` / `#ece8e1`, single accent `#c2410c`
- Route line colours functional only (row stripe, map polylines, legend)
- Custom `logo.svg` rail mark — not stock illustration
- Skeleton shimmer for loading states only (not decorative)
- `prefers-reduced-motion` global guard retained
- No purple/cyan gradients, no Inter, no AI marketing copy

### Still intentional (not slop)

- Severity colours (ok/warn/delay/bad) — functional status semantics per PRODUCT_RESEARCH
- Pulse strip name — disruption chip row, not animated glow
- KV schematic on Status tab — functional line picker, not marketing hero

