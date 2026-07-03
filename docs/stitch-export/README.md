# Stitch export — TrafficMY redesign

Imported from `stitch_task_execution_engine.zip` (Google Stitch).

## Files

| File | Screen |
|------|--------|
| `home/code.html` | Home — glance, Live today cards, filters, line board |
| `map/code.html` | Map — layer chips, dark map, pins, floating line card |
| `travel/code.html` | Travel — plan route, passes |
| `DESIGN.md` | **JomTransit** design system (tokens, typography, neubrutalist rules) |

## Design system highlights

- **Font:** Nunito Sans, weights 600–900
- **Style:** Tactile flat / neubrutalist — 2px borders, `0 4px 0` solid shadows
- **Primary green:** `#58CC02` · **Active blue:** `#2FB8FF`
- **Line colours:** unchanged (Kelana `#E31837`, KTM `#0066B3`, etc.)
- **Signal cards:** line stripe + RIDING NOW + source tag + time
- **BM/EN:** bilingual nav labels (Home/Utama, Map/Peta)

## Live app integration (partial)

- Signal cards in `static/js/app.js` + `play.css` updated to match Stitch Live today pattern
- Full Tailwind HTML **not** dropped in — ported to vanilla CSS (no CDN in production PWA)
- Map + Travel + header shell: still on Play UI — next pass can port from `map/code.html` and `travel/code.html`

## Preview Stitch mockups locally

Open any `code.html` in a browser (needs internet for Tailwind CDN + Google Fonts).
