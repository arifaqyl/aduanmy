from __future__ import annotations

import re

from app.core.files import load_yaml

_CATALOG: dict | None = None


def _catalog() -> dict:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = load_yaml("locations.yaml")
    return _CATALOG


def _places() -> dict[str, dict]:
    return _catalog().get("places", {})


def _state_aliases() -> dict[str, str]:
    return _catalog().get("state_aliases", {})


def _entity_states() -> dict[str, str]:
    return _catalog().get("entity_states", {})


def extract_location(text: str) -> str:
    low = text.lower()
    for token, meta in sorted(_places().items(), key=lambda item: len(item[0]), reverse=True):
        pattern = r"\b" + re.escape(token) + r"\b"
        if re.search(pattern, low):
            return meta.get("label", token.title())
    for alias, state in sorted(_state_aliases().items(), key=lambda item: len(item[0]), reverse=True):
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, low):
            return state
    return ""


def infer_state(*, text: str = "", location: str = "", entity: str = "", category: str = "") -> str:
    if location:
        loc_low = location.lower()
        for token, meta in _places().items():
            label = meta.get("label", "").lower()
            if loc_low == label or loc_low == token:
                return meta.get("state", "")
        for alias, state in _state_aliases().items():
            if loc_low == alias or loc_low == state.lower():
                return state

    if entity:
        hinted = _entity_states().get(entity, None)
        if hinted is not None:
            return hinted

    low = text.lower()
    for token, meta in sorted(_places().items(), key=lambda item: len(item[0]), reverse=True):
        pattern = r"\b" + re.escape(token) + r"\b"
        if re.search(pattern, low):
            return meta.get("state", "")
    for alias, state in sorted(_state_aliases().items(), key=lambda item: len(item[0]), reverse=True):
        pattern = r"\b" + re.escape(alias) + r"\b"
        if re.search(pattern, low):
            return state

    if category == "transport" and entity and entity.upper() in {"KTM", "KTMB"}:
        return ""
    return ""
