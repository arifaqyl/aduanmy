from datetime import UTC, datetime, timedelta

from app.collectors.threads.client import (
    _fill_missing_created_at,
    _is_recent_enough,
    _is_profile_discovery_candidate,
    _looks_like_pinned_preview,
)
from app.pipeline.extract import category_signal_ok, transport_incident_signal_ok


def test_fill_missing_created_at_backfills_only_missing_rows(monkeypatch):
    rows = [
        {"url": "https://threads.example/post/1", "created_at": ""},
        {"url": "https://threads.example/post/2", "created_at": "2026-06-21T04:18:43.000Z"},
    ]

    def fake_timestamps(urls: list[str]) -> dict[str, str]:
        assert urls == ["https://threads.example/post/1"]
        return {"https://threads.example/post/1": "2026-06-22T10:10:46.000Z"}

    monkeypatch.setattr("app.collectors.threads.client._playwright_post_timestamps", fake_timestamps)

    filled = _fill_missing_created_at(rows)

    assert filled[0]["created_at"] == "2026-06-22T10:10:46.000Z"
    assert filled[1]["created_at"] == "2026-06-21T04:18:43.000Z"


def test_looks_like_pinned_preview_flags_pinned_rows():
    assert _looks_like_pinned_preview("Pinned transit.taste.trail 05/14/26 something")
    assert not _looks_like_pinned_preview("transit.taste.trail 16h Tak boleh keluar stesen")


def test_profile_discovery_candidate_is_strict_for_transport():
    assert _is_profile_discovery_candidate(
        "transit.taste.trail 16h Tak boleh keluar stesen",
        "Tak boleh keluar stesen fire alarm kat MRT Maluri",
        "transport",
    )
    assert not _is_profile_discovery_candidate(
        "transit.taste.trail 1d Exit gate pulak problem",
        "",
        "transport",
    )
    assert not _is_profile_discovery_candidate(
        "transit.taste.trail 1d Jom jalan-jalan LRT3",
        "",
        "transport",
    )


def test_transport_incident_signal_accepts_live_line_breakdown_post():
    text = "Korang Mrt Kajang line problem ke? kenape tak gerak2 ni..."
    assert transport_incident_signal_ok(text)
    assert category_signal_ok(text, "transport", "Kajang Line")


def test_transport_incident_signal_rejects_property_and_lifestyle_mentions():
    assert not transport_incident_signal_ok(
        "FOR SALE condo dekat LRT Cempaka below market asking price RM235,000."
    )
    assert not transport_incident_signal_ok(
        "Located in Menara UOA Bangsar and connected with LRT Bangsar, serving really good pastries."
    )


def test_threads_recent_filter_rejects_old_posts():
    assert _is_recent_enough("2025-11-14T10:00:00Z") is False


def test_threads_recent_filter_accepts_recent_posts():
    recent = (datetime.now(UTC) - timedelta(days=5)).isoformat().replace("+00:00", "Z")
    assert _is_recent_enough(recent) is True
