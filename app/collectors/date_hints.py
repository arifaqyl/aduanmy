from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from app.collectors.common import clean_text

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def _iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _month_number(name: str) -> int | None:
    return _MONTHS.get(clean_text(name).lower())


def created_at_from_text(text: str, *, now: datetime | None = None) -> str:
    """Best-effort created_at from social post preview or og:description text."""
    text = clean_text(text)
    if not text:
        return ""
    current = now or datetime.now(UTC)

    absolute = re.search(
        r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
        text,
        re.I,
    )
    if absolute:
        month = _month_number(absolute.group(2))
        if month:
            try:
                return _iso_z(
                    datetime(
                        int(absolute.group(3)),
                        month,
                        int(absolute.group(1)),
                        tzinfo=UTC,
                    )
                )
            except ValueError:
                pass

    slash = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b", text)
    if slash:
        month = int(slash.group(1))
        day = int(slash.group(2))
        year = int(slash.group(3))
        if year < 100:
            year += 2000
        try:
            return _iso_z(datetime(year, month, day, tzinfo=UTC))
        except ValueError:
            pass

    year_hint = re.search(r"\b(20\d{2})\b", text)
    default_year = int(year_hint.group(1)) if year_hint else current.year

    parenthetical = re.search(
        r"\((?:\w+\s+)?(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\)",
        text,
        re.I,
    )
    if parenthetical:
        month = _month_number(parenthetical.group(1))
        if month:
            try:
                return _iso_z(datetime(default_year, month, int(parenthetical.group(2)), tzinfo=UTC))
            except ValueError:
                pass

    relative = re.search(r"\b(\d+)\s*([hdwm])\b", text.lower())
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        if unit == "h":
            delta = timedelta(hours=amount)
        elif unit == "d":
            delta = timedelta(days=amount)
        elif unit == "w":
            delta = timedelta(weeks=amount)
        else:
            delta = timedelta(days=amount * 30)
        return _iso_z(current - delta)

    return ""
