from starlette.testclient import TestClient

from app.main import create_app
from app.db.session import reset_complaints, upsert_complaints
from app.schemas.complaint import ComplaintSchema
from app.services.ingest_service import run_ingest


def test_root_serves_frontend_html():
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "TrafficMY" in response.text



def test_refresh_route_runs_ingest_and_returns_cluster_count():
    client = TestClient(create_app())
    response = client.post("/api/refresh")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "ingest" in payload
    assert "cluster_count" in payload


def test_trafficmy_overview_route_returns_product_shaped_payload():
    run_ingest()
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
    run_ingest()
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


def test_trafficmy_status_route_returns_freshness_payload():
    run_ingest()
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "TrafficMY"
    assert "freshness" in payload
    assert payload["freshness"]["freshness_basis"] in {"created_at", "inserted_at"}
    assert "ingest" in payload
    assert "top_wedge" in payload
    assert "written" in payload["ingest"]
    assert "threads" in payload["ingest"]
    assert "reddit" in payload["ingest"]
    assert "x" in payload["ingest"]


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
                created_at="2026-06-22T00:00:00Z",
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
                created_at="2026-06-22T00:00:00Z",
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
                created_at="2026-06-22T00:00:00Z",
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
