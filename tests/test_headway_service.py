"""Scheduled headway and rider-wait deviation.

The honesty properties matter more than the arithmetic: no deviation without
a measured wait, the band comes from the report's own time, and outside
service hours the answer is None rather than a comparison that does not apply.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime, timezone, timedelta

import pytest

from app.services import headway_service as H

MYT = timezone(timedelta(hours=8))


def _zip(tmp_path, freqs, trips, calendar):
    p = tmp_path / "rail.zip"
    with zipfile.ZipFile(p, "w") as zf:
        for name, rows in [("frequencies.txt", freqs), ("trips.txt", trips), ("calendar.txt", calendar)]:
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
            zf.writestr(name, buf.getvalue())
    return p


CAL = [
    {"service_id": "MonFri", "monday": "1", "tuesday": "1", "wednesday": "1", "thursday": "1",
     "friday": "1", "saturday": "0", "sunday": "0", "start_date": "20190101", "end_date": "20261231"},
    {"service_id": "Sat", "monday": "0", "tuesday": "0", "wednesday": "0", "thursday": "0",
     "friday": "0", "saturday": "1", "sunday": "0", "start_date": "20190101", "end_date": "20261231"},
]
TRIPS = [
    {"route_id": "KJ", "service_id": "MonFri", "trip_id": "KJL_MonFri_0", "direction_id": "0"},
    {"route_id": "KJ", "service_id": "MonFri", "trip_id": "KJL_MonFri_1", "direction_id": "1"},
    {"route_id": "KJ", "service_id": "Sat", "trip_id": "KJL_Sat_0", "direction_id": "0"},
]
FREQS = [
    {"trip_id": "KJL_MonFri_0", "start_time": "06:00:00", "end_time": "07:00:00", "headway_secs": "420"},
    {"trip_id": "KJL_MonFri_0", "start_time": "07:00:00", "end_time": "09:00:00", "headway_secs": "240"},
    {"trip_id": "KJL_MonFri_0", "start_time": "19:00:00", "end_time": "24:00:00", "headway_secs": "420"},
    # opposite direction publishes the same bands — must dedupe, not double
    {"trip_id": "KJL_MonFri_1", "start_time": "07:00:00", "end_time": "09:00:00", "headway_secs": "240"},
    {"trip_id": "KJL_Sat_0",    "start_time": "07:00:00", "end_time": "09:00:00", "headway_secs": "600"},
]


@pytest.fixture
def bands(tmp_path, monkeypatch):
    z = _zip(tmp_path, FREQS, TRIPS, CAL)
    monkeypatch.setattr(H, "load_headways", lambda force=False: H.parse_headways(z))
    return H.parse_headways(z)


def test_parse_dedupes_opposite_directions(bands):
    kj = bands["kelana-jaya"]
    peak = [b for b in kj if b.start_min == 420 and b.service_id == "MonFri"]
    assert len(peak) == 1
    assert peak[0].headway_min == 4


def test_parse_handles_gtfs_24_00_end_time(bands):
    late = [b for b in bands["kelana-jaya"] if b.start_min == 19 * 60][0]
    assert late.end_min == 1440
    assert late.label() == "19:00–00:00"


def test_weekday_peak_band(bands):
    tue_0744 = datetime(2026, 9, 1, 7, 44, tzinfo=MYT)   # Tuesday
    s = H.scheduled_headway("kelana-jaya", tue_0744)
    assert s == {"headway_min": 4, "band": "07:00–09:00", "service": "MonFri", "at_myt": "07:44"}


def test_saturday_uses_the_saturday_band_not_weekday(bands):
    sat_0744 = datetime(2026, 9, 5, 7, 44, tzinfo=MYT)
    assert H.scheduled_headway("kelana-jaya", sat_0744)["headway_min"] == 10


def test_outside_any_band_is_none(bands):
    """03:00 on a weekday: no service. Must not fall back to a nearby band."""
    assert H.scheduled_headway("kelana-jaya", datetime(2026, 9, 1, 3, 0, tzinfo=MYT)) is None


def test_band_is_chosen_by_utc_input_converted_to_myt(bands):
    """23:44 UTC Monday is 07:44 MYT Tuesday — peak, not off-peak."""
    utc = datetime(2026, 8, 31, 23, 44, tzinfo=timezone.utc)
    assert H.scheduled_headway("kelana-jaya", utc)["headway_min"] == 4


def test_iso_string_input_is_accepted(bands):
    assert H.scheduled_headway("kelana-jaya", "2026-09-01T07:44:00+08:00")["headway_min"] == 4


def test_unknown_line_is_none(bands):
    assert H.scheduled_headway("ktm-komuter") is None


# --- wait extraction ------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("waited 20 min at Bangsar, tak gerak", 20),
    ("kena tunggu 15 minit dekat masjid jamek", 15),
    ("stuck for 1 hour already", 60),
    ("delay dah 45 mins no announcement", 45),
])
def test_extract_wait_minutes(text, expected):
    assert H.extract_wait_minutes(text) == expected


def test_travel_time_is_not_a_wait():
    """A duration with no waiting cue is a journey time, not a platform wait."""
    assert H.extract_wait_minutes("15 min from KL Sentral to KLCC, smooth") is None


def test_absurd_duration_is_rejected():
    assert H.extract_wait_minutes("waited 5 hours lol") is None


def test_no_number_is_none():
    assert H.extract_wait_minutes("waiting so long at bangsar") is None


# --- deviation --------------------------------------------------------------

def test_deviation_reports_ratio_against_the_report_time_band(bands):
    d = H.deviation("kelana-jaya", 20, datetime(2026, 9, 1, 7, 44, tzinfo=MYT))
    assert d["scheduled_min"] == 4
    assert d["reported_min"] == 20
    assert d["ratio"] == 5.0
    assert d["label"] == "5× headway"
    assert d["band"] == "07:00–09:00"


def test_deviation_within_schedule_is_labelled_as_such(bands):
    d = H.deviation("kelana-jaya", 5, datetime(2026, 9, 1, 7, 44, tzinfo=MYT))
    assert d["ratio"] == 1.2
    assert d["label"] == "within schedule"


def test_no_measured_wait_means_no_deviation(bands):
    """The rule that keeps this honest: nothing is inferred from 'delay' alone."""
    assert H.deviation("kelana-jaya", None, datetime(2026, 9, 1, 7, 44, tzinfo=MYT)) is None
    assert H.deviation("kelana-jaya", 0, datetime(2026, 9, 1, 7, 44, tzinfo=MYT)) is None


def test_no_band_means_no_deviation_even_with_a_wait(bands):
    assert H.deviation("kelana-jaya", 20, datetime(2026, 9, 1, 3, 0, tzinfo=MYT)) is None
