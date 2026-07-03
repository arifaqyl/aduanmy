# TrafficMY open-source stack

Hybrid architecture: **Threads / social reports primary**, GTFS and official feeds secondary. This document lists OSS references used for code, data, and media assets.

## Signal priority

| Layer | Source | Role |
|-------|--------|------|
| 1 | Threads keyword search | Primary rider signal |
| 2 | Reddit / RSS | Corroboration |
| 3 | Official pages (MyRapid, KTMB) | Ground-truth notices |
| 4 | GTFS static | Station graph, journey planner |
| 5 | GTFS-RT | Optional bus GPS (map toggle, may lag) |

## Code & data references

| Project | Use in TrafficMY | License | URL |
|---------|------------------|---------|-----|
| [public-transport/generating-transit-maps](https://github.com/public-transport/generating-transit-maps) | Linear schematic generation patterns (`scripts/build_line_svgs.py`) | MIT | https://github.com/public-transport/generating-transit-maps |
| [juliuste/transit-map](https://github.com/juliuste/transit-map) | Metro-map pipeline concepts (reference) | MIT | https://github.com/juliuste/transit-map |
| [vasile/transit-map](https://github.com/vasile/transit-map) | SVG polyline composition (reference only) | Check repo | https://github.com/vasile/transit-map |
| [weareblahs/bus](https://github.com/weareblahs/bus) | Malaysia GTFS-RT bus layer pattern | Check repo | https://github.com/weareblahs/bus |
| [Tabler Icons](https://github.com/tabler/tabler-icons) | UI icons (train, bus, map-pin, transfer, clock) | MIT | https://github.com/tabler/tabler-icons |
| [Leaflet](https://github.com/Leaflet/Leaflet) | Map tab | BSD-2-Clause | https://github.com/Leaflet/Leaflet |
| [CARTO dark basemap](https://github.com/CartoDB/basemap-styles) | Map tiles | BSD / attribution | https://carto.com/attributions |
| [IBM Plex Sans](https://github.com/IBM/plex) | Typography (web + SVG labels) | OFL-1.1 | https://github.com/IBM/plex |
| Malaysia GTFS (data.gov.my) | Station graph, optional bus GPS | Open data terms | https://developer.data.gov.my |

## Media assets

All schematic artwork is **original Malaysia geometry** composed from reusable marker components — not AI-generated and not copied from TfL/MTR/MyRapid copyrighted maps.

| Asset path | Description | License / source |
|------------|-------------|------------------|
| `static/assets/icons/train.svg` | Tabler train outline | MIT — Tabler Icons |
| `static/assets/icons/bus.svg` | Tabler bus outline | MIT — Tabler Icons |
| `static/assets/icons/map-pin.svg` | Tabler map-pin | MIT — Tabler Icons |
| `static/assets/icons/transfer.svg` | Tabler transfer | MIT — Tabler Icons |
| `static/assets/icons/clock.svg` | Tabler clock | MIT — Tabler Icons |
| `static/assets/markers/stop-dot.svg` | Filled stop node | TrafficMY (pattern from generating-transit-maps) |
| `static/assets/markers/interchange-ring.svg` | Hollow interchange ring | TrafficMY (linear diagram convention) |
| `static/assets/markers/terminal-square.svg` | Terminal cap | TrafficMY |
| `static/lines/*.svg` | Per-line schematics | Generated — `python scripts/build_line_svgs.py` |
| `static/lines/*-thumb.svg` | Board thumbnails | Generated |
| `static/lines/kv-system.svg` | KV system schematic | Generated |
| `static/data/kv-system-map.svg` | KV system map copy | Generated |

Full per-file table: [`static/assets/README.md`](../static/assets/README.md).

### Build schematics

```bash
python scripts/build_line_svgs.py
```

Reads `static/data/line-stations.json` + `lines-reference.json`, composes markers from `static/assets/markers/`, writes:

- `static/lines/{line-id}.svg` and `{line-id}-thumb.svg`
- `static/assets/schematics/{alias}.svg` (e.g. `kajang-mrt.svg`, `lrt3-shah-alam.svg`)
- `static/data/kv-system-map.svg` and `static/lines/kv-system.svg`

### Rules

- No hotlinking or embedding copyrighted operator map artwork.
- Geometry patterns only from OSS literature; station names/order from public references.
- Legend swatches are CSS colour chips, not generated images.

## Usability (responsive UX)

Patterns borrowed from TfL Journey Planner, JR East station boards, and MyRapid line status — functional, not decorative.

| Breakpoint | Layout |
|------------|--------|
| Mobile `<768px` | Bottom nav (Status · Map · Plan · Passes), bottom-sheet Line Guide with drag handle, FAB refresh, header search bar, full-viewport map |
| Tablet `768–1024px` | Map tab split: line list ~40% + map |
| Desktop `>1024px` | Max-width 1200px, Line Guide as 400px right panel |

### Accessibility

- Status badges include text labels (`Normal`, `Delay`, `Disruption`) — not colour alone
- `aria-pressed` on map layer toggles; `role="tablist"` on main nav
- Focus trap + Escape closes drawer; `/` or `Ctrl/Cmd+K` focuses search
- `prefers-reduced-motion` disables animations
- Lazy-loaded Leaflet (map tab only) — does not block first paint

### Performance (mobile)

- Map GPS poll: 30s default; 60s when `navigator.connection.saveData` or slow 3G
- Schematic images use `loading="lazy"` in Line Guide

## API surfaces (Threads-first)

| Endpoint | Purpose |
|----------|---------|
| `GET /api/trafficmy/overview` | Board summary — social source group default |
| `GET /api/trafficmy/map/live` | Rider report pins + optional bus GPS + rail geometry |
| `GET /api/trafficmy/lines/{id}/info` | Line guide with schematic URL + rider reports |
| `GET /api/health` | Includes `threads_count`, `primary_signal: threads` |

## Live paths (after deploy)

| Resource | URL |
|----------|-----|
| App | https://arifaqyl.me/traffic/ |
| Health | https://arifaqyl.me/traffic/api/health |
| Live map API | https://arifaqyl.me/traffic/api/trafficmy/map/live |
| Line schematic | https://arifaqyl.me/traffic/static/lines/kelana-jaya.svg |
| KV system map | https://arifaqyl.me/traffic/static/lines/kv-system.svg |
