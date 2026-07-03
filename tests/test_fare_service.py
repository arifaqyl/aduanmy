from app.services.fare_service import estimate_journey_fare


def test_estimate_journey_fare_returns_bands():
    result = estimate_journey_fare(ride_legs=2, transfers=1)
    assert result["currency"] == "MYR"
    assert result["estimate_low"] <= result["estimate_typical"] <= result["estimate_high"]
    assert "disclaimer" in result
