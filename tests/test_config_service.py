from app.services.config_service import _lane_status, get_trafficmy_config


def test_empty_source_is_checked_quiet_not_degraded():
    assert _lane_status("reddit", 0, "empty") == "empty"


def test_trafficmy_config_includes_source_lanes():
    payload = get_trafficmy_config()
    assert payload["product"] == "TrafficMY"
    assert payload["live_window_days"] == 21
    assert payload["poll_interval_seconds"] >= 60
    assert payload["ingest_interval_seconds"] >= 60
    assert payload["gtfs_ingest_interval_seconds"] >= 60
    assert payload["gtfs_anomaly_enabled"] is False
    assert payload["threads_authenticated_session_enabled"] is False
    lane_ids = {lane["id"] for lane in payload["source_lanes"]}
    assert lane_ids == {"threads", "official", "gtfs", "reddit", "rss", "x"}
    x_lane = next(item for item in payload["source_lanes"] if item["id"] == "x")
    assert x_lane["status"] in {"active", "dormant", "degraded"}
    gtfs_lane = next(item for item in payload["source_lanes"] if item["id"] == "gtfs")
    assert gtfs_lane["status"] == "reference"
