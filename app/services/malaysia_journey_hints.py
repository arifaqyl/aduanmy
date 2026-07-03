from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.services.transport_update_service import compare_rapid_passes

_INTERCHANGES_PATH = Path(__file__).resolve().parents[2] / "static" / "data" / "interchanges-my.json"

_ROUTE_TO_LINE = {
    "KJL": "kelana-jaya",
    "SPL": "ampang-sri-petaling",
    "AGL": "ampang-sri-petaling",
    "SPG": "ampang-sri-petaling",
    "PYL": "putrajaya",
    "KGL": "kajang",
    "MRL": "monorail",
    "BRT": "brt-sunway",
}


@lru_cache(maxsize=1)
def _interchange_data() -> dict:
    if not _INTERCHANGES_PATH.is_file():
        return {"stations": {}, "operator_notes": {}}
    return json.loads(_INTERCHANGES_PATH.read_text(encoding="utf-8"))


def _normalise_station(name: str) -> str:
    return " ".join(name.lower().replace("'", "").replace("-", " ").split())


def lookup_station_hint(station_name: str) -> dict | None:
    stations = _interchange_data().get("stations") or {}
    return stations.get(_normalise_station(station_name))


def operator_commuter_note(line_id: str, *, lang: str = "en") -> str | None:
    notes = _interchange_data().get("operator_notes") or {}
    row = notes.get(line_id)
    if not row:
        return None
    return row.get("ms" if lang == "ms" else "en")


def _enrich_transfer_leg(leg: dict) -> dict:
    station = leg.get("to") or leg.get("from") or ""
    hint = lookup_station_hint(station)
    if not hint:
        return leg
    enriched = dict(leg)
    enriched["interchange_hint"] = {
        "station": hint.get("name", station),
        "walk_min": hint.get("walk_min"),
        "indoor": hint.get("indoor"),
        "paid_separate": bool(hint.get("paid_separate")),
        "note_en": hint.get("note_en", ""),
        "note_ms": hint.get("note_ms", ""),
        "ets_warning_en": hint.get("ets_warning_en"),
        "ets_warning_ms": hint.get("ets_warning_ms"),
    }
    return enriched


def journey_fare_guidance(*, ride_legs: int, transfers: int, typical_fare: float) -> dict:
    """Malaysia-specific fare truth for Rapid KL GTFS journeys."""
    pass_compare = compare_rapid_passes(
        rides_per_month=max(20, ride_legs * 22),
        average_fare=max(typical_fare, 2.5),
        malaysian=True,
        student=False,
    )
    recommendation = pass_compare.get("recommendation") or {}
    notes_en = [
        "Rapid KL rail only — this planner does not route KTM Komuter, buses or KLIA Ekspres.",
        "My50 covers unlimited Rapid KL rail + bus for Malaysians (RM50/mo) — not KTM.",
        "Connecting Prasarana ↔ KTMB requires separate tickets; tap out at the gate.",
    ]
    notes_ms = [
        "Rapid KL sahaja — perancang ini tidak merangkumi KTM Komuter, bas atau KLIA Ekspres.",
        "My50 merangkumi tanpa had Rapid KL rel + bas untuk rakyat Malaysia (RM50/bulan) — bukan KTM.",
        "Pertukaran Prasarana ↔ KTMB perlukan tiket berasingan; tap keluar di pintu.",
    ]
    return {
        "planner_scope": "rapid_kl_rail",
        "my50_covers_route": True,
        "ktm_included": False,
        "separate_operator_warning": transfers > 0,
        "notes_en": notes_en,
        "notes_ms": notes_ms,
        "pass_fit": {
            "recommended": recommendation.get("name"),
            "recommended_id": recommendation.get("id"),
            "monthly_cost": recommendation.get("monthly_cost"),
            "estimated_saving": pass_compare.get("estimated_saving"),
            "break_even_rides": recommendation.get("break_even_rides"),
            "note": recommendation.get("note"),
        },
    }


def enrich_journey_plan(plan: dict) -> dict:
    legs = []
    line_ids: list[str] = []
    for leg in plan.get("legs") or []:
        if leg.get("kind") == "transfer":
            legs.append(_enrich_transfer_leg(leg))
        else:
            legs.append(leg)
            short = leg.get("short_name") or ""
            line_id = _ROUTE_TO_LINE.get(short)
            if line_id:
                line_ids.append(line_id)
    plan = dict(plan)
    plan["legs"] = legs
    fare = plan.get("fare") or {}
    typical = float(fare.get("estimate_typical") or 2.5)
    ride_legs = sum(1 for leg in legs if leg.get("kind") == "ride")
    plan["malaysia"] = journey_fare_guidance(
        ride_legs=ride_legs,
        transfers=int(plan.get("transfers") or 0),
        typical_fare=typical,
    )
    plan["line_ids_on_route"] = line_ids
    paid_transfers = [
        leg["interchange_hint"]
        for leg in legs
        if leg.get("kind") == "transfer" and (leg.get("interchange_hint") or {}).get("paid_separate")
    ]
    if paid_transfers:
        plan["malaysia"]["paid_transfer_stations"] = [row["station"] for row in paid_transfers]
    return plan
