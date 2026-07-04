from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

RECENT_DAYS = 3
LIVE_WINDOW_DAYS = 21
MYT = timezone(timedelta(hours=8))


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def classify_freshness(
    value: str | None,
    *,
    now: datetime | None = None,
    recent_days: int = RECENT_DAYS,
    live_window_days: int = LIVE_WINDOW_DAYS,
) -> tuple[str, int | None]:
    parsed = parse_dt(value)
    if parsed is None:
        return "unknown", None
    current = now or datetime.now(UTC)
    age_days = max(0, int((current - parsed).total_seconds() // 86400))
    if parsed >= current - timedelta(days=recent_days):
        return "recent", age_days
    if parsed >= current - timedelta(days=live_window_days):
        return "aging", age_days
    return "stale", age_days


def myt_day_start(*, now: datetime | None = None) -> datetime:
    """Midnight at the start of the current MYT calendar day (timezone-aware UTC)."""
    current = (now or datetime.now(UTC)).astimezone(MYT)
    start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(UTC)


def myt_today_date(*, now: datetime | None = None):
    return (now or datetime.now(UTC)).astimezone(MYT).date()


def is_myt_peak_hour(*, now: datetime | None = None) -> bool:
    """True during KL commute rush — 07:00-10:00 and 17:00-20:00 MYT."""
    hour = (now or datetime.now(UTC)).astimezone(MYT).hour
    return (7 <= hour < 10) or (17 <= hour < 20)


def is_inside_myt_today(
    value: str | None,
    *,
    now: datetime | None = None,
) -> bool:
    """True when the timestamp falls on today's calendar date in Malaysia (MYT)."""
    parsed = parse_dt(value)
    if parsed is None:
        return False
    return parsed.astimezone(MYT).date() == myt_today_date(now=now)


def is_inside_hours(
    value: str | None,
    *,
    hours: int = 24,
    now: datetime | None = None,
) -> bool:
    parsed = parse_dt(value)
    if parsed is None:
        return False
    current = now or datetime.now(UTC)
    return parsed >= current - timedelta(hours=hours)


def is_inside_live_window(
    value: str | None,
    *,
    now: datetime | None = None,
    live_window_days: int = LIVE_WINDOW_DAYS,
) -> bool:
    parsed = parse_dt(value)
    if parsed is None:
        return False
    current = now or datetime.now(UTC)
    return parsed >= current - timedelta(days=live_window_days)
