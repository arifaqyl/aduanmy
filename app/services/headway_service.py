"""Scheduled headway per line, and how far a rider's reported wait deviates from it.

This is the one claim TrafficMY can make that nothing else in Malaysia does.
There is no realtime rail feed — every GTFS-RT endpoint on data.gov.my was
probed: vehicle positions only, no trip updates, no service alerts, and the
rail feed 404s. But the *static* feed carries frequencies.txt, the operator's
own timetable of how often a train is meant to run in each time band.

That turns a rider post from a vibe into a measurement:

    "waited 20 min at Bangsar"     +   KJ weekday 07:00-09:00: every 4 min
    -> reported 20 min, scheduled 4 min, ~5x headway

Honesty rules this module keeps:
  * a deviation is only produced when a report contains a measured wait.
    Nothing is inferred from "delay" alone.
  * the band is chosen by the report's own MYT time, not by when the board
    is viewed. A 07:44 report is judged against the 07:00-09:00 band.
  * outside service hours, or with no band, it returns None rather than
    comparing against a headway that does not apply.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

from app.core.freshness import parse_dt

MYT = timezone(timedelta(hours=8))
NETWORK = "rapid-rail-kl"

# GTFS route_id -> TrafficMY line id. AG and PH share a board row and, in the
# operator's timetable, identical headway bands.
ROUTE_TO_LINE = {
    "KJ": "kelana-jaya",
    "AG": "ampang-sri-petaling",
    "PH": "ampang-sri-petaling",
    "SA": "lrt3",
    "KGL": "kajang",
    "PYL": "putrajaya",
    "MR": "monorail",
    "BRT": "brt-sunway",
}

_DAY_COLS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Same shape as public_incident_service._RELATIVE_TIME_RE, kept local so this
# module has no dependency on presentation code.
_DURATION_RE = re.compile(r"\b(\d{1,3})\s*(min|mins|minute|minutes|minit|jam|hour|hours|hr|hrs)\b", re.I)
# A duration only counts as a *wait* when the post is about waiting. Without
# this, "15 min from KL Sentral" (a travel time) would read as a 15 min wait.
_WAIT_CUE_RE = re.compile(
    r"\b(?:wait|waiting|waited|tunggu|menunggu|kena tunggu|delay|delayed|lambat|"
    r"kelewatan|stuck|stucked|tak gerak|tak bergerak|not moving|berhenti|stop lama)\b",
    re.I,
)
_MAX_PLATFORM_WAIT_MIN = 180  # beyond this it is not a platform wait being described


@dataclass(frozen=True)
class Band:
    days: frozenset[int]     # 0=Mon .. 6=Sun
    start_min: int           # minutes from midnight; may exceed 1440 per GTFS
    end_min: int
    headway_min: int
    service_id: str

    def label(self) -> str:
        return f"{_fmt(self.start_min)}–{_fmt(self.end_min)}"


def _fmt(minutes: int) -> str:
    h, m = divmod(minutes % 1440, 60)
    return f"{h:02d}:{m:02d}"


def _hhmmss_to_min(value: str) -> int:
    """GTFS allows 24:00:00 and beyond for service past midnight."""
    parts = value.strip().split(":")
    h, m = int(parts[0]), int(parts[1])
    return h * 60 + m


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------

_cache: dict[str, object] = {"key": None, "bands": {}}


def _read(zf: zipfile.ZipFile, name: str) -> list[dict]:
    with zf.open(name) as f:
        return list(csv.DictReader(io.TextIOWrapper(f, "utf-8-sig")))


def parse_headways(zip_path: Path) -> dict[str, list[Band]]:
    with zipfile.ZipFile(zip_path) as zf:
        calendar = _read(zf, "calendar.txt")
        trips = _read(zf, "trips.txt")
        freqs = _read(zf, "frequencies.txt")

    service_days: dict[str, frozenset[int]] = {
        row["service_id"]: frozenset(i for i, col in enumerate(_DAY_COLS) if row.get(col) == "1")
        for row in calendar
    }
    trip_meta = {t["trip_id"]: (t.get("route_id", ""), t.get("service_id", "")) for t in trips}

    out: dict[str, set[Band]] = {}
    for f in freqs:
        route_id, service_id = trip_meta.get(f["trip_id"], ("", ""))
        line_id = ROUTE_TO_LINE.get(route_id)
        days = service_days.get(service_id)
        if not line_id or not days:
            continue
        try:
            band = Band(
                days=days,
                start_min=_hhmmss_to_min(f["start_time"]),
                end_min=_hhmmss_to_min(f["end_time"]),
                headway_min=max(1, int(f["headway_secs"]) // 60),
                service_id=service_id,
            )
        except (KeyError, ValueError):
            continue
        # both directions publish the same band; a set dedupes them
        out.setdefault(line_id, set()).add(band)

    return {k: sorted(v, key=lambda b: (b.start_min, b.service_id)) for k, v in out.items()}


def warm_headways(*, force: bool = False) -> int:
    """Download (or refresh) the GTFS zip. Call from the scheduler, never from
    a request path. Returns the number of lines with bands, 0 on failure."""
    from app.collectors.gtfs.static_client import download_static

    try:
        zip_path = download_static(NETWORK, force=force)
    except Exception:
        return len(load_headways())
    _cache["key"] = None            # force a re-parse on next read
    return len(load_headways())


def load_headways() -> dict[str, list[Band]]:
    """Cache-only. Never touches the network.

    A board render must not block on data.gov.my, and a test suite building
    boards must not hammer it — doing so returned 429s. If nothing has been
    downloaded yet, this returns {} and every lookup degrades to None, which
    the UI renders as "no schedule available" rather than a wrong number.
    """
    from app.collectors.gtfs.static_client import _cache_path

    zip_path = _cache_path(NETWORK)
    if not zip_path.exists():
        return {}
    key = (str(zip_path), zip_path.stat().st_mtime)
    if _cache["key"] != key:
        try:
            _cache["bands"] = parse_headways(zip_path)
        except Exception:
            return {}
        _cache["key"] = key
    return _cache["bands"]  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# lookups
# ---------------------------------------------------------------------------

def _to_myt(at: datetime | str | None) -> datetime:
    if at is None:
        return datetime.now(MYT)
    if isinstance(at, str):
        parsed = parse_dt(at)
        at = parsed if parsed is not None else datetime.now(UTC)
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    return at.astimezone(MYT)


def scheduled_headway(line_id: str, at: datetime | str | None = None) -> dict | None:
    """The operator's scheduled headway for this line at the given MYT moment."""
    bands = load_headways().get(line_id)
    if not bands:
        return None
    local = _to_myt(at)
    weekday = local.weekday()
    mod = local.hour * 60 + local.minute

    # GTFS bands can run past 24:00 and belong to the *previous* service day.
    candidates = [(weekday, mod), ((weekday - 1) % 7, mod + 1440)]
    for day, minute in candidates:
        for b in bands:
            if day in b.days and b.start_min <= minute < b.end_min:
                return {
                    "headway_min": b.headway_min,
                    "band": b.label(),
                    "service": b.service_id,
                    "at_myt": local.strftime("%H:%M"),
                }
    return None


def extract_wait_minutes(text: str) -> int | None:
    """A measured platform wait in minutes, or None if the post has none."""
    if not text or not _WAIT_CUE_RE.search(text):
        return None
    m = _DURATION_RE.search(text)
    if not m:
        return None
    qty, unit = int(m.group(1)), m.group(2).lower()
    minutes = qty * 60 if unit.startswith(("jam", "hour", "hr")) else qty
    if minutes <= 0 or minutes > _MAX_PLATFORM_WAIT_MIN:
        return None
    return minutes


def deviation(line_id: str, wait_min: int | None, at: datetime | str | None = None) -> dict | None:
    """Reported wait against scheduled headway. None unless both are real."""
    if not wait_min:
        return None
    sched = scheduled_headway(line_id, at)
    if not sched:
        return None
    ratio = wait_min / sched["headway_min"]
    if ratio < 1.5:
        label = "within schedule"
    else:
        label = f"{ratio:.0f}× headway" if ratio >= 3 else f"{ratio:.1f}× headway"
    return {
        "scheduled_min": sched["headway_min"],
        "reported_min": wait_min,
        "ratio": round(ratio, 1),
        "label": label,
        "band": sched["band"],
        "service": sched["service"],
        "at_myt": sched["at_myt"],
    }
