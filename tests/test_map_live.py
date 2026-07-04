from unittest.mock import patch

from starlette.testclient import TestClient

from app.main import create_app


def test_map_live_returns_threads_first_payload():
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/map/live")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "TrafficMY"
    assert payload["primary_source"] == "community"
    assert "reports" in payload
    assert "vehicles" in payload
    assert payload["vehicles"] == []
    assert "rail_lines" in payload
    assert payload["bounds"]["south"] < payload["bounds"]["north"]
    assert "disclaimers" in payload
    assert "vehicles" in payload["disclaimers"]
    for report in payload["reports"]:
        if report.get("lat") is not None and report.get("lon") is not None:
            assert isinstance(report["lat"], (int, float))
            assert isinstance(report["lon"], (int, float))
    for hub in payload.get("interchanges") or []:
        assert isinstance(hub.get("lat"), (int, float))
        assert isinstance(hub.get("lon"), (int, float))


def test_map_live_vehicles_optional():
    fake_buses = [
        {"lat": 3.14, "lon": 101.69, "route_id": "T800", "age_seconds": 42},
    ]
    with patch(
        "app.collectors.gtfs.rt_client.fetch_bus_vehicle_positions",
        return_value=fake_buses,
    ), patch(
        "app.collectors.gtfs.rt_client.fetch_rail_vehicle_positions",
        return_value=[],
    ):
        client = TestClient(create_app())
        off = client.get("/api/trafficmy/map/live")
        on = client.get("/api/trafficmy/map/live?vehicles=true")
    assert off.status_code == 200
    assert on.status_code == 200
    assert off.json()["vehicles"] == []
    assert len(on.json()["vehicles"]) == 1
    assert on.json()["vehicles"][0]["route_id"] == "T800"
