from app.services.malaysia_journey_hints import (
    enrich_journey_plan,
    journey_fare_guidance,
    lookup_station_hint,
    operator_commuter_note,
)


def test_lookup_kl_sentral_has_paid_separate_warning():
    hint = lookup_station_hint("KL Sentral")
    assert hint is not None
    assert hint["paid_separate"] is True
    assert "Tap out" in hint["note_en"]
    assert "Tap keluar" in hint["note_ms"]


def test_operator_commuter_note_for_ktm():
    note = operator_commuter_note("ktm-komuter")
    assert note is not None
    assert "30 min" in note
    note_ms = operator_commuter_note("ktm-komuter", lang="ms")
    assert "KTMB" in note_ms


def test_enrich_journey_adds_malaysia_block():
    plan = {
        "transfers": 1,
        "legs": [
            {"kind": "ride", "short_name": "KJL", "line": "Kelana Jaya Line"},
            {
                "kind": "transfer",
                "from": "Masjid Jamek",
                "to": "Masjid Jamek",
                "minutes": 4,
            },
            {"kind": "ride", "short_name": "AGL", "line": "Ampang Line"},
        ],
        "fare": {"estimate_typical": 3.0},
    }
    enriched = enrich_journey_plan(plan)
    assert enriched["malaysia"]["planner_scope"] == "rapid_kl_rail"
    assert enriched["malaysia"]["my50_covers_route"] is True
    assert enriched["line_ids_on_route"] == ["kelana-jaya", "ampang-sri-petaling"]
    transfer = enriched["legs"][1]
    assert transfer["interchange_hint"]["station"] == "Masjid Jamek"


def test_journey_fare_guidance_includes_pass_fit():
    guidance = journey_fare_guidance(ride_legs=2, transfers=1, typical_fare=3.0)
    assert guidance["ktm_included"] is False
    assert guidance["pass_fit"]["recommended_id"]
