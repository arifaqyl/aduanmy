from __future__ import annotations

from app.pipeline.geo import _places


def list_stations(*, q: str = "", limit: int = 20) -> list[dict]:
    """Return deduplicated place labels from locations.yaml for autocomplete."""
    needle = (q or "").strip().lower()
    seen: set[str] = set()
    items: list[dict] = []

    for token, meta in _places().items():
        label = meta.get("label") or token.title()
        if label in seen:
            continue
        state = meta.get("state", "")
        haystack = f"{label} {token} {state}".lower()
        if needle and needle not in haystack:
            continue
        seen.add(label)
        items.append({"label": label, "token": token, "state": state})
        if len(items) >= limit:
            break

    items.sort(key=lambda row: row["label"].lower())
    return items
