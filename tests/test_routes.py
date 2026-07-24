from datetime import timedelta

from starlette.testclient import TestClient

from app.core.freshness import myt_day_start
from app.main import create_app
from app.db.session import reset_complaints, upsert_complaints
from app.schemas.complaint import ComplaintSchema


def _today_iso(hours: int = 0, minutes: int = 0) -> str:
    return (myt_day_start() + timedelta(hours=hours, minutes=minutes)).isoformat().replace("+00:00", "Z")


def test_root_serves_frontend_html():
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "TrafficMY" in response.text


def test_methodology_page_and_api():
    client = TestClient(create_app())
    page = client.get("/methodology")
    assert page.status_code == 200
    assert "How it works" in page.text
    api = client.get("/api/trafficmy/methodology")
    assert api.status_code == 200
    payload = api.json()
    assert payload["product"] == "TrafficMY"
    assert payload["not_official"] is True
    assert payload["windows"]["live_window_days"] == 21
    assert payload["windows"]["status_window_hours"] == 24
    assert any(s["id"] == "threads" for s in payload["sources"])



def test_refresh_route_runs_ingest_and_returns_cluster_count(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.incidents.run_full_now",
        lambda: {"written": 1, "threads": 1},
    )
    client = TestClient(create_app())
    response = client.post("/api/refresh?sync=true")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "ingest" in payload
    assert "cluster_count" in payload


def test_trafficmy_overview_route_returns_product_shaped_payload():
    reset_complaints()
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "TrafficMY"
    assert "summary" in payload
    assert "top_incidents" in payload
    assert "stale_hidden_count" in payload["summary"]
    assert payload["summary"]["include_stale"] is False


def test_trafficmy_incidents_route_returns_filtered_payload():
    reset_complaints()
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/incidents?confidence_band=strong")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "TrafficMY"
    assert payload["filters"]["confidence_band"] == "strong"
    assert payload["filters"]["include_stale"] is False
    assert "items" in payload
    if payload["items"]:
        assert payload["items"][0]["freshness_bucket"] in {"recent", "aging", "stale", "unknown"}


def test_trafficmy_overview_route_accepts_include_stale_flag():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="recent",
                url="https://example.com/recent",
                author_handle="u1",
                created_at="2026-06-21T04:18:43Z",
                raw_text="MRT fire alarm at Maluri",
                normalized_text="mrt fire alarm at maluri",
                detected_language_mix="en",
                category="transport",
                entity="MRT",
                location="Maluri",
                severity="high",
                confidence=0.8,
                cluster_id="transport:MRT:Maluri:incident",
            ),
            ComplaintSchema(
                source_platform="x",
                post_id="stale",
                url="https://example.com/stale",
                author_handle="askrapidkl",
                created_at="2026-05-12T11:50:51Z",
                raw_text="Kelana Jaya Line delay",
                normalized_text="kelana jaya line delay",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Bangsar",
                severity="medium",
                confidence=0.6,
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            ),
        ]
    )
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/overview?include_stale=true")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["include_stale"] is True
    assert payload["summary"]["transport_cluster_count"] == 2


def test_trafficmy_status_route_returns_freshness_payload(monkeypatch):
    reset_complaints()
    monkeypatch.setattr(
        "app.services.status_service._latest_ingest_summary",
        lambda: {"written": 0, "threads": 0, "reddit": 0, "x": 0, "rss": 0},
    )
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "TrafficMY"
    assert "freshness" in payload
    assert payload["freshness"]["freshness_basis"] in {"created_at", "inserted_at", "none"}
    assert "ingest" in payload
    assert "top_wedge" in payload
    assert "written" in payload["ingest"]
    assert "threads" in payload["ingest"]
    assert "reddit" in payload["ingest"]
    assert "x" in payload["ingest"]
    assert "rss" in payload["ingest"]


def test_health_route_returns_db_and_scheduler_state():
    client = TestClient(create_app())
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "trafficmy"
    assert payload["db_ok"] is True
    assert "complaint_count" in payload
    assert "scheduler" in payload


def test_refresh_route_rejects_wrong_api_key(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "refresh_api_key", "secret-key")
    monkeypatch.setattr(settings, "allow_dashboard_refresh", False)
    monkeypatch.setattr(
        "app.api.routes.incidents.trigger_full_ingest_async",
        lambda: True,
    )
    client = TestClient(create_app())
    response = client.post("/api/refresh")
    assert response.status_code == 401
    ok = client.post("/api/refresh", headers={"X-API-Key": "secret-key"})
    assert ok.status_code == 200


def test_refresh_route_allows_dashboard_header(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "refresh_api_key", "secret-key")
    monkeypatch.setattr(settings, "allow_dashboard_refresh", True)
    monkeypatch.setattr(
        "app.api.routes.incidents.trigger_full_ingest_async",
        lambda: True,
    )
    client = TestClient(create_app())
    response = client.post("/api/refresh", headers={"X-Dashboard-Refresh": "1"})
    assert response.status_code == 200


def test_refresh_route_requires_same_origin_dashboard_in_production(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "refresh_api_key", "secret-key")
    monkeypatch.setattr(settings, "allow_dashboard_refresh", True)
    monkeypatch.setattr(
        "app.api.routes.incidents.trigger_full_ingest_async",
        lambda: True,
    )
    client = TestClient(create_app())
    blocked = client.post(
        "/api/refresh",
        headers={"X-Dashboard-Refresh": "1", "Referer": "https://evil.example/traffic/"},
    )
    assert blocked.status_code == 401
    allowed = client.post(
        "/api/refresh",
        headers={"X-Dashboard-Refresh": "1", "Referer": "http://testserver/traffic/"},
    )
    assert allowed.status_code == 200


def test_refresh_allowed_constant_time_compare_handles_none_and_wrong(monkeypatch):
    from app.api.routes.incidents import _refresh_allowed
    from app.core.config import settings

    # No configured key -> refresh is open (dev default).
    monkeypatch.setattr(settings, "refresh_api_key", "")
    assert _refresh_allowed(x_api_key=None, referer=None, dashboard_header=None) is True

    # Configured key: correct key accepted; wrong / None / mismatched-length keys
    # rejected without raising (locks the secrets.compare_digest path).
    monkeypatch.setattr(settings, "refresh_api_key", "secret-key")
    monkeypatch.setattr(settings, "allow_dashboard_refresh", False)
    assert _refresh_allowed(x_api_key="secret-key", referer=None, dashboard_header=None) is True
    assert _refresh_allowed(x_api_key="wrong", referer=None, dashboard_header=None) is False
    assert _refresh_allowed(x_api_key=None, referer=None, dashboard_header=None) is False
    assert _refresh_allowed(x_api_key="x", referer=None, dashboard_header=None) is False


def test_telegram_webhook_secret_constant_time(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "telegram_bot_token", "bot-token")
    monkeypatch.setattr(settings, "telegram_webhook_secret", "webhook-secret")
    client = TestClient(create_app())

    # Wrong / mismatched-length / empty secrets all 403 (no 500) — locks the
    # secrets.compare_digest path so a timing-safe compare stays timing-safe.
    assert client.post("/api/telegram/webhook?secret=wrong", json={"message": {}}).status_code == 403
    assert client.post("/api/telegram/webhook?secret=x", json={"message": {}}).status_code == 403
    assert client.post("/api/telegram/webhook", json={"message": {}}).status_code == 403


def test_refresh_route_rejects_overlapping_ingest(monkeypatch):
    monkeypatch.setattr("app.api.routes.incidents.trigger_full_ingest_async", lambda: False)
    client = TestClient(create_app())
    response = client.post("/api/refresh")
    assert response.status_code == 409


def test_trafficmy_config_route():
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["live_window_days"] == 21
    assert len(payload["source_lanes"]) == 6


def test_trafficmy_brand_and_shell_routes():
    client = TestClient(create_app())
    brand = client.get("/api/trafficmy/brand")
    assert brand.status_code == 200
    brand_payload = brand.json()
    assert brand_payload["name"] == "TrafficMY Pulse"
    assert brand_payload["mobile_first"] is True

    shell = client.get("/api/trafficmy/app-shell")
    assert shell.status_code == 200
    shell_payload = shell.json()
    assert "brand" in shell_payload
    assert "config" in shell_payload
    assert "meta" in shell_payload
    assert "status" in shell_payload
    assert "freshness" in shell_payload["status"]


def test_trafficmy_stations_route():
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/stations?q=maluri&limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "locations.yaml"
    assert any(item["label"] == "Maluri" for item in payload["items"])


def test_trafficmy_map_stations_route(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.journey.get_map_stations",
        lambda limit=120, layer="rail": {"product": "TrafficMY", "stations": [], "bounds": {}},
    )
    response = TestClient(create_app()).get("/api/trafficmy/map/stations")
    assert response.status_code == 200
    assert response.json()["product"] == "TrafficMY"


def test_journey_plan_includes_fare(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.journey.plan_rail_journey",
        lambda origin, destination: {
            "legs": [{"kind": "ride"}, {"kind": "transfer"}, {"kind": "ride"}],
            "transfers": 1,
            "total_minutes": 32,
        },
    )
    response = TestClient(create_app()).get("/api/trafficmy/journey/plan?origin=Gombak&destination=KLCC")
    assert response.status_code == 200
    assert "fare" in response.json()
    assert response.json()["fare"]["currency"] == "MYR"


def test_journey_station_route_uses_search_service(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.journey.list_rail_stations",
        lambda query, limit: [{"name": "KLCC", "lines": ["KJL"]}],
    )
    response = TestClient(create_app()).get("/api/trafficmy/journey/stations?q=klcc&limit=5")
    assert response.status_code == 200
    assert response.json()["items"][0]["name"] == "KLCC"
    assert response.json()["source"] == "Malaysia government GTFS"


def test_journey_plan_route_returns_route_and_handles_bad_place(monkeypatch):
    monkeypatch.setattr(
        "app.api.routes.journey.plan_rail_journey",
        lambda origin, destination: {"origin": origin, "destination": destination, "minutes": 18},
    )
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/journey/plan?origin=Gombak&destination=KLCC")
    assert response.status_code == 200
    assert response.json()["minutes"] == 18

    def fail_plan(origin, destination):
        raise ValueError("Place not found in Malaysia")

    monkeypatch.setattr("app.api.routes.journey.plan_rail_journey", fail_plan)
    assert client.get("/api/trafficmy/journey/plan?origin=Unknown&destination=KLCC").status_code == 422


def test_transport_updates_and_pass_comparison_routes():
    client = TestClient(create_app())
    updates = client.get("/api/trafficmy/updates")
    assert updates.status_code == 200
    assert updates.json()["product"] == "TrafficMY"
    comparison = client.get(
        "/api/trafficmy/pass-comparison?rides_per_month=20&average_fare=3&malaysian=true&student=true"
    )
    assert comparison.status_code == 200
    assert comparison.json()["recommendation"]["id"] == "rapid-pelajar"


def test_trafficmy_status_prefers_signal_age_over_insert_time_for_staleness():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="x",
                post_id="old-x",
                url="https://example.com/old-x",
                author_handle="askrapidkl",
                created_at="2026-05-12T11:50:51Z",
                raw_text="older but valid signal",
                normalized_text="older but valid signal",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Bangsar",
                severity="low",
                confidence=0.4,
                cluster_id="transport:LRT:Bangsar:delay",
            )
        ]
    )
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["freshness"]["freshness_basis"] == "created_at"
    assert payload["freshness"]["is_stale"] is True


def test_trafficmy_incident_detail_route_returns_product_shaped_detail():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="x",
                post_id="x1",
                url="https://example.com/x1",
                author_handle="askrapidkl",
                created_at=_today_iso(),
                raw_text="LRT incident",
                normalized_text="lrt incident kelana jaya line",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Kelana Jaya",
                severity="high",
                confidence=0.9,
                cluster_id="transport:LRT:Kelana Jaya:incident",
            )
        ]
    )
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/incidents/transport:LRT:Kelana Jaya:incident")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "TrafficMY"
    assert payload["incident"]["cluster_id"] == "transport:LRT:Kelana Jaya:incident"
    assert payload["incident"]["headline"]
    assert "example_text" not in payload["incident"]
    assert "raw_text" not in payload["items"][0]
    assert "author_handle" not in payload["items"][0]
    assert len(payload["items"]) == 1


def test_trafficmy_incident_detail_route_accepts_slash_in_cluster_id():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/t1",
                author_handle="thestaronline",
                created_at=_today_iso(),
                raw_text="Ampang and Sri Petaling line disruption at Chan Sow Lin",
                normalized_text="ampang sri petaling line disruption at chan sow lin",
                detected_language_mix="en",
                category="transport",
                entity="Ampang/Sri Petaling Line",
                location="Chan Sow Lin",
                severity="high",
                confidence=0.9,
                cluster_id="transport:Ampang/Sri Petaling Line:Chan Sow Lin:delay",
            )
        ]
    )
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/incidents/transport:Ampang/Sri%20Petaling%20Line:Chan%20Sow%20Lin:delay")
    assert response.status_code == 200
    payload = response.json()
    assert payload["incident"]["cluster_id"] == "transport:Ampang/Sri Petaling Line:Chan Sow Lin:delay"


def test_trafficmy_overview_route_includes_counted_entities_and_locations():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="x",
                post_id="x1",
                url="https://example.com/x1",
                author_handle="askrapidkl",
                created_at=_today_iso(),
                raw_text="LRT incident",
                normalized_text="lrt incident kelana jaya line",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Kelana Jaya",
                severity="high",
                confidence=0.9,
                cluster_id="transport:LRT:Kelana Jaya:incident",
            )
        ]
    )
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["transport_entities"][0]["name"] == "LRT"
    assert payload["transport_entities"][0]["count"] == 1
    assert payload["transport_locations"][0]["name"] == "Kelana Jaya"
    assert payload["transport_locations"][0]["count"] == 1
