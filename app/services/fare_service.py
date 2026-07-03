from __future__ import annotations

import json
from functools import lru_cache

from app.core.files import project_root

_DEFAULT_FARES = {
    "source": "MyRapid cashless fare structure (public summary)",
    "disclaimer": "Estimate only. Actual fare depends on zones, concessions, and operator.",
    "currency": "MYR",
    "rapid_kl": {"cashless_min": 1.0, "cashless_max": 6.4, "typical_commute": 2.5},
    "estimate_rules": {"base": 1.2, "per_ride_leg": 1.8, "per_transfer": 0.5},
}


@lru_cache(maxsize=1)
def _fares() -> dict:
    path = project_root() / "static" / "data" / "fares.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return _DEFAULT_FARES


def estimate_journey_fare(*, ride_legs: int, transfers: int = 0) -> dict:
    """Rome2Rio-style fare hint from static Rapid KL bands — not live ticketing."""
    cfg = _fares()
    rules = cfg["estimate_rules"]
    rapid = cfg["rapid_kl"]
    rides = max(1, ride_legs)
    low = rules["base"] + rides * rules["per_ride_leg"] * 0.85
    high = min(rapid["cashless_max"], rules["base"] + rides * rules["per_ride_leg"] + transfers * rules["per_transfer"])
    typical = round(min(rapid["typical_commute"] * rides, rapid["cashless_max"]), 2)
    return {
        "currency": cfg["currency"],
        "estimate_low": round(max(rapid["cashless_min"], low), 2),
        "estimate_high": round(max(high, typical), 2),
        "estimate_typical": typical,
        "disclaimer": cfg["disclaimer"],
        "source": cfg["source"],
    }
