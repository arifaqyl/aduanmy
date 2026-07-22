from __future__ import annotations

from app.pipeline.geo import _places

_ROUTE_SHORT_TO_LINE = {
    "KJL": "kelana-jaya",
    "AGL": "ampang-sri-petaling",
    "SPL": "ampang-sri-petaling",
    "KGL": "kajang",
    "PYL": "putrajaya",
    "MRL": "monorail",
    "SAL": "lrt3",
}


def list_stations(*, q: str = "", limit: int = 20) -> list[dict]:
    """Canonical station autocomplete: GTFS rail first, YAML places as fallback."""
    needle = (q or "").strip().lower()
    items: list[dict] = []

    try:
        from app.services.journey_service import list_rail_stations

        for row in list_rail_stations(q, limit=limit):
            shorts = row.get("lines") or []
            line_ids = []
            for short in shorts:
                lid = _ROUTE_SHORT_TO_LINE.get(str(short).upper())
                if lid and lid not in line_ids:
                    line_ids.append(lid)
            items.append(
                {
                    "label": row["name"],
                    "name": row["name"],
                    "token": row["name"],
                    "state": "",
                    "lines": shorts,
                    "line_ids": line_ids,
                    "lat": row.get("lat"),
                    "lon": row.get("lon"),
                    "source": "gtfs",
                }
            )
    except Exception:
        items = []

    if items:
        return items

    seen: set[str] = set()
    for token, meta in _places().items():
        label = meta.get("label") or token.title()
        if label in seen:
            continue
        state = meta.get("state", "")
        haystack = f"{label} {token} {state}".lower()
        if needle and needle not in haystack:
            continue
        seen.add(label)
        items.append(
            {
                "label": label,
                "name": label,
                "token": token,
                "state": state,
                "lines": [],
                "line_ids": [],
                "source": "locations.yaml",
            }
        )
        if len(items) >= limit:
            break

    items.sort(key=lambda row: row["label"].lower())
    return items
