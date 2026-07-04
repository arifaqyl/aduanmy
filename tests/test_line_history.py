from datetime import timedelta

from starlette.testclient import TestClient

from app.core.freshness import myt_day_start
from app.db.session import reset_complaints, upsert_complaints
from app.main import create_app
from app.schemas.complaint import ComplaintSchema
from app.services.line_history_service import get_line_history


def _today_iso(hours: int = 9) -> str:
    return (myt_day_start() + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def _complaint(**overrides) -> ComplaintSchema:
    base = dict(
        source_platform="threads",
        post_id="p1",
        url="https://threads.example/p1",
        author_handle="rider",
        created_at=_today_iso(),
        raw_text="Kelana Jaya Line train stuck at Bangsar now",
        normalized_text="kelana jaya line train stuck at bangsar now",
        detected_language_mix="en",
        category="transport",
        subcategory="rail",
        entity="Kelana Jaya Line",
        location="Bangsar",
        severity="medium",
        confidence=0.8,
        cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
    )
    base.update(overrides)
    return ComplaintSchema(**base)


def test_get_line_history_unknown_line_returns_none():
    assert get_line_history("not-a-real-line") is None


def test_get_line_history_counts_todays_matching_rider_signal():
    reset_complaints()
    upsert_complaints([_complaint(post_id="today-1")])

    history = get_line_history("kelana-jaya")
    assert history is not None
    assert history["line_id"] == "kelana-jaya"
    assert len(history["daily_counts"]) == 14
    assert history["today"]["count"] == 1
    assert history["daily_counts"][-1]["count"] == 1


def test_get_line_history_ignores_weak_non_signal_rows():
    reset_complaints()
    upsert_complaints(
        [
            _complaint(
                post_id="weak-1",
                raw_text="LRT ok je today, nothing special",
                normalized_text="lrt ok je today nothing special",
            )
        ]
    )
    history = get_line_history("kelana-jaya")
    assert history["today"]["count"] == 0


def test_line_history_api_endpoint_returns_payload():
    reset_complaints()
    upsert_complaints([_complaint(post_id="api-1")])
    client = TestClient(create_app())
    res = client.get("/api/trafficmy/lines/kelana-jaya/history")
    assert res.status_code == 200
    payload = res.json()
    assert payload["line_id"] == "kelana-jaya"
    assert "heatmap" in payload
    assert payload["today"]["count"] == 1


def test_line_history_api_endpoint_404_for_unknown_line():
    client = TestClient(create_app())
    res = client.get("/api/trafficmy/lines/not-a-real-line/history")
    assert res.status_code == 404
