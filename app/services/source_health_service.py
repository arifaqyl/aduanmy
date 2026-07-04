from __future__ import annotations

from datetime import UTC, datetime

from app.core.freshness import parse_dt
from app.db.session import connect, init_db

# Threads is the primary rider-signal lane. If it comes back empty this many
# consecutive ingests (roughly 45 min at a 15-min cadence), flag it loudly rather
# than silently degrading into an official-notice mirror.
CONSECUTIVE_EMPTY_ALERT_THRESHOLD = 3


def _consecutive_empty_counts(conn) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT source, status, row_count
        FROM collector_runs
        WHERE status != 'paused'
        ORDER BY source, id DESC
        """
    ).fetchall()
    counts: dict[str, int] = {}
    seen_break: set[str] = set()
    for row in rows:
        source = row["source"]
        if source in seen_break:
            continue
        if row["status"] == "failed" or int(row["row_count"] or 0) == 0:
            counts[source] = counts.get(source, 0) + 1
        else:
            seen_break.add(source)
    return counts


def get_source_health() -> list[dict]:
    init_db()
    with connect() as conn:
        latest = conn.execute(
            """
            SELECT cr.run_id, cr.source, cr.started_at, cr.finished_at,
                   cr.status, cr.row_count, cr.duration_seconds, cr.error
            FROM collector_runs AS cr
            JOIN (
                SELECT source, MAX(id) AS latest_id
                FROM collector_runs
                GROUP BY source
            ) AS recent ON recent.latest_id = cr.id
            ORDER BY cr.source
            """
        ).fetchall()
        nonempty = {
            row["source"]: row["last_nonempty_at"]
            for row in conn.execute(
                """
                SELECT source, MAX(finished_at) AS last_nonempty_at
                FROM collector_runs
                WHERE row_count > 0
                GROUP BY source
                """
            ).fetchall()
        }
        consecutive_empty = _consecutive_empty_counts(conn)

    now = datetime.now(UTC)
    items: list[dict] = []
    for row in latest:
        item = dict(row)
        finished = parse_dt(item.get("finished_at"))
        age_minutes = None if finished is None else max(0.0, (now - finished).total_seconds() / 60)
        item["age_minutes"] = round(age_minutes, 1) if age_minutes is not None else None
        item["last_nonempty_at"] = nonempty.get(item["source"])
        item["available"] = item["status"] not in {"failed"}
        item["consecutive_empty_runs"] = consecutive_empty.get(item["source"], 0)
        item["needs_attention"] = item["consecutive_empty_runs"] >= CONSECUTIVE_EMPTY_ALERT_THRESHOLD
        items.append(item)
    return items
