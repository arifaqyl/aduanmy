from __future__ import annotations

from datetime import UTC, datetime

from app.core.freshness import parse_dt
from app.db.session import connect, init_db


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

    now = datetime.now(UTC)
    items: list[dict] = []
    for row in latest:
        item = dict(row)
        finished = parse_dt(item.get("finished_at"))
        age_minutes = None if finished is None else max(0.0, (now - finished).total_seconds() / 60)
        item["age_minutes"] = round(age_minutes, 1) if age_minutes is not None else None
        item["last_nonempty_at"] = nonempty.get(item["source"])
        item["available"] = item["status"] not in {"failed"}
        items.append(item)
    return items
