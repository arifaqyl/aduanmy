from datetime import UTC, datetime, timedelta

from app.core.freshness import parse_dt


def test_is_inside_myt_today_respects_malaysia_midnight():
    from datetime import timezone

    from app.core.freshness import is_inside_myt_today

    myt = timezone(timedelta(hours=8))
    today_noon = datetime(2026, 7, 2, 12, 0, tzinfo=myt).astimezone(UTC)
    yesterday_noon = datetime(2026, 7, 1, 12, 0, tzinfo=myt).astimezone(UTC)
    assert is_inside_myt_today(today_noon.isoformat(), now=today_noon)
    assert not is_inside_myt_today(yesterday_noon.isoformat(), now=today_noon)


def test_parse_dt_sqlite_format_is_utc():
    parsed = parse_dt("2026-06-28 06:48:31")
    assert parsed is not None
    assert parsed.tzinfo == UTC
    assert parsed.hour == 6


def test_parse_dt_iso_z():
    parsed = parse_dt("2026-06-25T00:48:11.000Z")
    assert parsed is not None
    assert parsed.tzinfo == UTC
