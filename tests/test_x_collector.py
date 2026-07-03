from datetime import UTC, datetime, timedelta

from app.collectors.x.client import (
    _is_recent_enough,
    _is_x_row_signal,
    _looks_like_pinned_preview,
    _syndication_profile_status_urls,
    _x_created_at_from_status_url,
)


def test_x_created_at_from_status_url_derives_real_timestamp():
    created_at = _x_created_at_from_status_url("https://x.com/myrapidkl/status/1589847935327817728")
    assert created_at.startswith("2022-11-08T")
    assert created_at.endswith("Z")


def test_recent_filter_rejects_old_status_dates():
    assert _is_recent_enough("2022-11-08T10:00:00Z") is False


def test_recent_filter_accepts_recent_status_dates():
    recent = (datetime.now(UTC) - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    assert _is_recent_enough(recent) is True


def test_looks_like_pinned_preview_flags_pinned_rows():
    assert _looks_like_pinned_preview("Pinned Ask Rapid KL @askrapidkl Apr 16, 2025 update")
    assert not _looks_like_pinned_preview("Kelana Jaya Line Update: incident on train 40")


def test_is_x_row_signal_accepts_trusted_transport_incident_text():
    text = "Kelana Jaya Line Update: LRT Kelana Jaya line is experiencing an incident."
    assert _is_x_row_signal(text, handle="askrapidkl")
    assert not _is_x_row_signal(
        "Our X support channel is now focused on service updates and announcements.",
        handle="askrapidkl",
    )


def test_syndication_profile_status_urls_extracts_status_links(monkeypatch):
    def fake_fetch_html(url: str, *, headers=None, timeout: int = 20) -> str:
        assert "askrapidkl" in url
        return '<a href="https://x.com/askrapidkl/status/1912322923005898946">tweet</a>'

    monkeypatch.setattr("app.collectors.x.client.fetch_html", fake_fetch_html)

    urls = _syndication_profile_status_urls("https://x.com/askrapidkl")

    assert urls == ["https://x.com/askrapidkl/status/1912322923005898946"]
