from datetime import UTC, datetime, timedelta

from app.collectors.date_hints import created_at_from_text


def test_created_at_from_text_parses_absolute_date():
    created_at = created_at_from_text("05 June 2026: Five passengers on the Kelana Jaya Line were injured.")
    assert created_at == "2026-06-05T00:00:00Z"


def test_created_at_from_text_parses_parenthetical_month_day():
    now = datetime(2026, 6, 27, tzinfo=UTC)
    created_at = created_at_from_text(
        "Automatic safety system activated on Thursday evening (June 4).",
        now=now,
    )
    assert created_at == "2026-06-04T00:00:00Z"


def test_created_at_from_text_parses_relative_hours():
    now = datetime(2026, 6, 27, 12, 0, tzinfo=UTC)
    created_at = created_at_from_text("transit.taste.trail 16h Tak boleh keluar stesen", now=now)
    assert created_at == "2026-06-26T20:00:00Z"


def test_created_at_from_text_parses_slash_date():
    created_at = created_at_from_text("Pinned transit.taste.trail 05/14/26 something")
    assert created_at == "2026-05-14T00:00:00Z"
