"""Line history — "is this normal?" daily/hourly rider-signal volume for one line.

This answers the question a pure ridership-stats dashboard can't: not "how many people
rode the Kelana Jaya Line today" but "are today's rider complaints unusual for a Tuesday
at 6pm, compared to the last two weeks?" It is built entirely from the same rider-signal
rows already collected for the live board — no new data source required.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.core.freshness import MYT, parse_dt
from app.core.transport_lines import LINE_CATALOG, match_transport_line
from app.db.session import connect, init_db
from app.pipeline.extract import transport_incident_signal_ok, transport_rider_signal_worthwhile

HISTORY_WINDOW_DAYS = 14
RIDER_SIGNAL_SOURCES = {"threads", "reddit", "rss"}
WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _line_ids() -> set[str]:
    return {spec["id"] for spec in LINE_CATALOG}


def _row_is_real_signal(row: dict) -> bool:
    if row.get("subcategory") == "line_info":
        return False
    text = row.get("raw_text") or row.get("normalized_text") or ""
    if not text.strip():
        return False
    entity = row.get("entity") or ""
    if row.get("source_platform") in RIDER_SIGNAL_SOURCES:
        return transport_rider_signal_worthwhile(text, entity)
    return transport_incident_signal_ok(text, entity)


def _fetch_transport_rows(*, since: datetime) -> list[dict]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT source_platform, created_at, raw_text, normalized_text, entity,
                   location, subcategory, cluster_id
            FROM complaints
            WHERE category = 'transport' AND created_at >= ?
            """,
            (since.isoformat(),),
        ).fetchall()
    return [dict(row) for row in rows]


def get_line_history(line_id: str, *, days: int = HISTORY_WINDOW_DAYS) -> dict | None:
    if line_id not in _line_ids():
        return None

    now = datetime.now(UTC)
    since = now - timedelta(days=days)
    rows = _fetch_transport_rows(since=since)

    daily_counts: dict[str, int] = defaultdict(int)
    weekday_hour_counts: dict[tuple[int, int], int] = defaultdict(int)
    matched_rows = 0

    for row in rows:
        if not _row_is_real_signal(row):
            continue
        if match_transport_line(row) != line_id:
            continue
        created = parse_dt(row.get("created_at"))
        if created is None:
            continue
        local = created.astimezone(MYT)
        date_key = local.date().isoformat()
        daily_counts[date_key] += 1
        weekday_hour_counts[(local.weekday(), local.hour)] += 1
        matched_rows += 1

    today_myt = now.astimezone(MYT).date()
    series = []
    for offset in range(days - 1, -1, -1):
        d = today_myt - timedelta(days=offset)
        key = d.isoformat()
        series.append({"date": key, "weekday": WEEKDAY_LABELS[d.weekday()], "count": daily_counts.get(key, 0)})

    today_count = daily_counts.get(today_myt.isoformat(), 0)
    today_weekday = today_myt.weekday()
    same_weekday_counts = [
        item["count"]
        for item in series
        if item["date"] != today_myt.isoformat() and WEEKDAY_LABELS[today_weekday] == item["weekday"]
    ]
    typical_count = round(statistics.median(same_weekday_counts), 1) if same_weekday_counts else None

    comparison = "no_baseline"
    if typical_count is not None:
        if typical_count == 0:
            comparison = "elevated" if today_count > 0 else "typical"
        elif today_count >= typical_count * 1.5:
            comparison = "elevated"
        elif today_count <= typical_count * 0.5:
            comparison = "quieter_than_usual"
        else:
            comparison = "typical"

    heatmap = [
        {"weekday": WEEKDAY_LABELS[wd], "hour": hour, "count": count}
        for (wd, hour), count in sorted(weekday_hour_counts.items())
    ]

    return {
        "line_id": line_id,
        "window_days": days,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "total_signals": matched_rows,
        "daily_counts": series,
        "today": {
            "date": today_myt.isoformat(),
            "weekday": WEEKDAY_LABELS[today_weekday],
            "count": today_count,
            "typical_for_weekday": typical_count,
            "comparison": comparison,
        },
        "heatmap": heatmap,
    }
