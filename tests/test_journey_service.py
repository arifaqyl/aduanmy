from datetime import date

from app.services import journey_service
from app.services.transport_update_service import compare_rapid_passes, get_transport_updates


def _tiny_graph() -> dict:
    stops = {
        "a": {"id": "a", "name": "Alpha", "lat": 3.0, "lon": 101.0, "route_id": "red", "accessible": True},
        "b": {"id": "b", "name": "Central", "lat": 3.01, "lon": 101.01, "route_id": "red", "accessible": True},
        "c": {"id": "c", "name": "Central", "lat": 3.0101, "lon": 101.0101, "route_id": "blue", "accessible": True},
        "d": {"id": "d", "name": "Delta", "lat": 3.02, "lon": 101.02, "route_id": "blue", "accessible": True},
    }
    return {
        "stops": stops,
        "routes": {
            "red": {"name": "Red Line", "short_name": "RED", "color": "#ff0000"},
            "blue": {"name": "Blue Line", "short_name": "BLU", "color": "#0000ff"},
        },
        "names": {"alpha": ["a"], "central": ["b", "c"], "delta": ["d"]},
        "adjacency": {
            "a": {"b": {"minutes": 5, "kind": "ride", "route_id": "red"}},
            "b": {"c": {"minutes": 3, "kind": "transfer", "distance_metres": 20}},
            "c": {"d": {"minutes": 6, "kind": "ride", "route_id": "blue"}},
            "d": {},
        },
    }


def test_plan_rail_journey_groups_lines_and_transfer(monkeypatch):
    monkeypatch.setattr(journey_service, "_graph", _tiny_graph)
    monkeypatch.setattr(
        journey_service,
        "_route_alerts_for_legs",
        lambda legs: ([], set()),
    )
    result = journey_service.plan_rail_journey("Alpha", "Delta")
    assert result["total_minutes"] == 14
    assert result["transfers"] == 1
    assert [leg["kind"] for leg in result["legs"]] == ["ride", "transfer", "ride"]
    assert result["route_alerts"] == []
    assert result["alternate"] is None


def _graph_with_parallel() -> dict:
    """Primary A→B on red; alternate A→C→B on blue avoids red."""
    stops = {
        "a": {"id": "a", "name": "Alpha", "lat": 3.0, "lon": 101.0, "route_id": "red", "accessible": True},
        "b": {"id": "b", "name": "Bravo", "lat": 3.02, "lon": 101.02, "route_id": "red", "accessible": True},
        "c": {"id": "c", "name": "Charlie", "lat": 3.01, "lon": 101.01, "route_id": "blue", "accessible": True},
    }
    return {
        "stops": stops,
        "routes": {
            "red": {"name": "Kelana Jaya Line", "short_name": "KJL", "color": "#ff0000"},
            "blue": {"name": "MRT Kajang Line", "short_name": "KGL", "color": "#0000ff"},
        },
        "names": {"alpha": ["a"], "bravo": ["b"], "charlie": ["c"]},
        "adjacency": {
            "a": {
                "b": {"minutes": 5, "kind": "ride", "route_id": "red"},
                "c": {"minutes": 4, "kind": "ride", "route_id": "blue"},
            },
            "c": {"b": {"minutes": 4, "kind": "ride", "route_id": "blue"}},
            "b": {},
        },
    }


def test_plan_rail_journey_returns_alternate_when_line_disrupted(monkeypatch):
    monkeypatch.setattr(journey_service, "_graph", _graph_with_parallel)

    def fake_alerts(legs):
        shorts = {leg.get("short_name") for leg in legs if leg.get("kind") == "ride"}
        if "KJL" in shorts:
            return (
                [{"line_id": "kelana-jaya", "name": "Kelana Jaya Line", "status": "delay", "status_label": "Delay"}],
                {"red"},
            )
        return ([], set())

    monkeypatch.setattr(journey_service, "_route_alerts_for_legs", fake_alerts)
    result = journey_service.plan_rail_journey("Alpha", "Bravo")
    assert result["route_alerts"][0]["line_id"] == "kelana-jaya"
    assert result["alternate"] is not None
    assert all(leg.get("short_name") != "KJL" for leg in result["alternate"]["legs"] if leg.get("kind") == "ride")


def test_station_search_groups_interchange_lines(monkeypatch):
    monkeypatch.setattr(journey_service, "_graph", _tiny_graph)
    result = journey_service.list_rail_stations("central")
    assert result[0]["name"] == "Central"
    assert result[0]["lines"] == ["BLU", "RED"]


def test_updates_expire_and_mark_upcoming():
    before_launch = get_transport_updates(today=date(2026, 6, 28))
    assert any(item["id"] == "lrt-shah-alam-launch" for item in before_launch["active"])
    assert any(item["id"] == "lrt-shah-alam-free" for item in before_launch["upcoming"])
    after_campaign = get_transport_updates(today=date(2026, 7, 29))
    assert not any(item["id"] == "lrt-shah-alam-free" for item in after_campaign["active"])


def test_pass_comparison_recommends_student_fare_when_cheapest():
    result = compare_rapid_passes(rides_per_month=20, average_fare=3, malaysian=True, student=True)
    assert result["recommendation"]["id"] == "rapid-pelajar"
    assert result["estimated_saving"] == 30


def test_pass_comparison_recommends_my50_for_frequent_malaysian():
    result = compare_rapid_passes(rides_per_month=44, average_fare=3, malaysian=True, student=False)
    assert result["recommendation"]["id"] == "my50"
    assert result["estimated_saving"] == 82
