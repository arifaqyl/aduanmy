from app.pipeline.bus_alerts import classify_transport_mode, is_mass_bus_alert, parse_myrapid_official


def test_parse_myrapid_bus_mass_alert():
    parsed = parse_myrapid_official("Kelewatan Bas: 8 Laluan Terjejas")
    assert parsed["entity"] == "RapidKL Bus"
    assert parsed["subcategory"] == "bus"
    assert parsed["severity"] == "high"
    assert parsed["affected_routes"] == 8


def test_parse_myrapid_rail_line():
    parsed = parse_myrapid_official("Kemas Kini: Laluan Kelana Jaya (LRT Kerinchi)")
    assert parsed.get("subcategory") == "rail"


def test_is_mass_bus_alert():
    assert is_mass_bus_alert("Kelewatan Bas: 3 Laluan Terjejas")
    assert not is_mass_bus_alert("Kelana Jaya Line delay at Bangsar")


def test_classify_transport_mode_bus_from_entity():
    assert classify_transport_mode(text="", entity="RapidKL Bus", subcategory="") == "bus"
