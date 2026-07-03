"""Tests for line reference API and service status."""
from datetime import UTC, datetime, timezone, timedelta

from starlette.testclient import TestClient

from app.main import create_app
from app.db.session import reset_complaints, upsert_complaints
from app.schemas.complaint import ComplaintSchema
from app.services.line_reference_service import compute_service_status_now

_MYT = timezone(timedelta(hours=8))


def test_lines_reference_includes_operating_hours():
    client = TestClient(create_app())
    res = client.get("/api/trafficmy/lines/reference")
    assert res.status_code == 200
    payload = res.json()
    kelana = next(line for line in payload["lines"] if line["id"] == "kelana-jaya")
    assert kelana.get("operating_hours")
    assert kelana["operating_hours"]["first_train"] == "06:00"
    assert kelana.get("service_status_now")


def test_line_info_endpoint():
    client = TestClient(create_app())
    res = client.get("/api/trafficmy/lines/kelana-jaya/info")
    assert res.status_code == 200
    payload = res.json()
    assert payload["reference"]["id"] == "kelana-jaya"
    assert payload.get("operating_hours")
    assert payload.get("service_status_now")
    assert "interchanges" in payload["reference"]


def test_line_info_never_republishes_raw_rider_copy():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="private-phrasing",
                url="https://threads.example/private-phrasing",
                author_handle="private-user",
                created_at=datetime.now(UTC).isoformat(),
                raw_text="DISTINCTIVE PRIVATE RIDER WORDING Kelana Jaya train stuck at Bangsar now",
                normalized_text="distinctive private rider wording kelana jaya train stuck at bangsar now",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Bangsar",
                subcategory="rail",
                severity="medium",
                confidence=0.8,
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            )
        ]
    )
    response = TestClient(create_app()).get("/api/trafficmy/lines/kelana-jaya/info")
    assert response.status_code == 200
    assert "DISTINCTIVE PRIVATE RIDER WORDING" not in response.text
    assert "private-user" not in response.text
    report = response.json()["rider_reports"][0]
    assert report["headline"] == "Possible delays on Kelana Jaya Line"
    assert "summary" in report


def test_service_status_before_and_after_service():
    hours = {"first_train": "06:00", "last_train": "23:30", "peak_hours": []}
    before = datetime(2026, 6, 28, 4, 30, tzinfo=_MYT)
    after = datetime(2026, 6, 28, 23, 45, tzinfo=_MYT)
    assert compute_service_status_now(hours, now=before.astimezone(timezone.utc))["status"] == "before_service"
    assert compute_service_status_now(hours, now=after.astimezone(timezone.utc))["status"] == "after_service"


def test_transport_incident_accepts_lrt3_preview_rides():
    from app.pipeline.extract import transport_incident_signal_ok, transport_line_info_signal_ok

    preview = "LRT3 Shah Alam Line free rides until July for preview passengers"
    assert transport_incident_signal_ok(preview) is False
    assert transport_line_info_signal_ok(preview) is True
