from datetime import UTC, datetime, timedelta

from app.collectors.x.client import _is_recent_enough, _x_created_at_from_status_url


def test_x_created_at_from_status_url_derives_real_timestamp():
    created_at = _x_created_at_from_status_url("https://x.com/myrapidkl/status/1589847935327817728")
    assert created_at.startswith("2022-11-08T")
    assert created_at.endswith("Z")


def test_recent_filter_rejects_old_status_dates():
    assert _is_recent_enough("2022-11-08T10:00:00Z") is False


def test_recent_filter_accepts_recent_status_dates():
    recent = (datetime.now(UTC) - timedelta(days=7)).isoformat().replace("+00:00", "Z")
    assert _is_recent_enough(recent) is True
