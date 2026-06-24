from __future__ import annotations

from datetime import UTC, datetime, timedelta

RECENT_DAYS = 3
LIVE_WINDOW_DAYS = 21


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
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
