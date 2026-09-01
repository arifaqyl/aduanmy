"""The deviation reaches the board row, end to end.

A rider report with a measured wait, on a line that is in service at the time
the board is viewed, must surface as headway + deviation on that line's row.
The same report viewed while the line is closed must not — a closed line's
board row is "ended for today", and no live figure should be derived from it.
"""
from __future__ import annotations

import shutil
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core.config import settings
from app.db.session import connect, init_db
from app.services import headway_service as H
from app.services.line_status_service import get_line_status_board

MYT = timezone(timedelta(hours=8))
REPO_ZIP = Path(__file__).resolve().parents[1] / "data" / "gtfs" / "cache" / "rapid-rail-kl.zip"


@pytest.fixture
def warm_cache():
    """Copy the committed GTFS zip into the isolated test data_dir so reads
    are cache-only (no network) but real bands are available."""
    if not REPO_ZIP.exists():
        pytest.skip("no cached GTFS zip in repo")
    dest = Path(settings.data_dir) / "gtfs" / "cache" / "rapid-rail-kl.zip"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO_ZIP, dest)
    H._cache["key"] = None
    yield
    H._cache["key"] = None


def _seed(created_at_myt: datetime, text: str):
    init_db()
    ts = created_at_myt.astimezone(UTC).isoformat().replace("+00:00", "Z")
    with connect() as conn:
        conn.execute(
            """INSERT INTO complaints (source_platform,post_id,url,author_handle,created_at,raw_text,
               normalized_text,detected_language_mix,category,subcategory,entity,location,severity,
               confidence,engagement,cluster_id,state)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("threads", "t-dev-0", "https://x.invalid/0", "rider", ts, text, text.lower(), "en,ms",
             "transport", "service_disruption", "Kelana Jaya Line", "Bangsar", "medium", 0.9, "{}",
             "t-dev-kj", "Selangor"),
        )


def _tuesday_at(h, m):
    # a fixed weekday so the MonFri band applies regardless of when tests run
    return datetime(2026, 9, 1, h, m, tzinfo=MYT)


def _line(board, line_id):
    return next(l for l in board["lines"] if l["id"] == line_id)


def test_measured_wait_in_service_yields_deviation(warm_cache):
    _seed(_tuesday_at(7, 44), "waited 20 min at bangsar, kelana jaya line tak gerak langsung")
    kj = _line(get_line_status_board(now=_tuesday_at(7, 50).astimezone(UTC)), "kelana-jaya")

    assert kj["in_service"] is True
    assert kj["report_count"] >= 1
    assert kj["reported_wait_min"] == 20
    assert kj["headway"]["headway_min"] == 4          # KJ weekday 07:00–09:00
    assert kj["headway"]["band"] == "07:00–09:00"
    assert kj["deviation"]["ratio"] == 5.0
    assert kj["deviation"]["label"] == "5× headway"


def test_band_follows_the_report_time_not_the_view_time(warm_cache):
    """Report at 07:44 (peak, every 4 min) viewed at 10:30 (off-peak, every 7)
    must still be judged against the 07:00–09:00 band it happened in."""
    _seed(_tuesday_at(7, 44), "waited 20 min at bangsar, kelana jaya line tak gerak")
    kj = _line(get_line_status_board(now=_tuesday_at(10, 30).astimezone(UTC)), "kelana-jaya")
    assert kj["headway"]["band"] == "07:00–09:00"
    assert kj["deviation"]["scheduled_min"] == 4


def test_report_without_a_number_gives_headway_but_no_deviation(warm_cache):
    _seed(_tuesday_at(7, 44), "kelana jaya line delay again, tak gerak at bangsar")
    kj = _line(get_line_status_board(now=_tuesday_at(7, 50).astimezone(UTC)), "kelana-jaya")
    assert kj["report_count"] >= 1
    assert kj["reported_wait_min"] is None
    assert kj["headway"] is not None      # the schedule is still shown
    assert kj["deviation"] is None        # but nothing is inferred


def test_closed_line_suppresses_reports_and_deviation(warm_cache):
    """The service-hours gate: viewed at 03:30 the line is closed, so the row
    reads ended-for-today and no live figure is derived from the report."""
    _seed(_tuesday_at(7, 44), "waited 20 min at bangsar, kelana jaya line tak gerak")
    kj = _line(get_line_status_board(now=_tuesday_at(3, 30).astimezone(UTC)), "kelana-jaya")
    assert kj["in_service"] is False
    assert kj["report_count"] == 0
    assert kj["headway"] is None
    assert kj["deviation"] is None
