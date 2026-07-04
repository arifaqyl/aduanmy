from app.services.signals_api_service import get_today_signals


def test_today_signals_api_shape():
    payload = get_today_signals(limit=5)
    assert payload["product"] == "TrafficMY"
    assert payload["schema_version"] == "1"
    assert payload["kind"] == "live_rider_signals_today"
    assert "status_date_myt" in payload
    assert "summary" in payload
    assert payload["summary"]["quiet_is_not_all_clear"] is True
    assert isinstance(payload["lines"], list)
    assert isinstance(payload["signals"], list)
    assert "differentiator" in payload
    assert "ridership" in payload["differentiator"].lower() or "statistics" in payload["differentiator"].lower()
