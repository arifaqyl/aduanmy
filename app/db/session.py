from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.core.config import settings
from app.schemas.complaint import ComplaintSchema


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    url TEXT NOT NULL,
    author_handle TEXT NOT NULL,
    created_at TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    detected_language_mix TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT NOT NULL,
    entity TEXT NOT NULL,
    location TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL,
    confidence REAL NOT NULL,
    engagement TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    inserted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_platform, post_id)
);

CREATE TABLE IF NOT EXISTS collector_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT NOT NULL,
    status TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    duration_seconds REAL NOT NULL DEFAULT 0,
    error TEXT NOT NULL DEFAULT '',
    UNIQUE(run_id, source)
);

CREATE INDEX IF NOT EXISTS idx_collector_runs_source_id
ON collector_runs(source, id DESC);

CREATE TABLE IF NOT EXISTS telegram_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT NOT NULL,
    line_id TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(chat_id, line_id)
);

CREATE INDEX IF NOT EXISTS idx_telegram_subscriptions_line
ON telegram_subscriptions(line_id);

CREATE TABLE IF NOT EXISTS line_status_snapshots (
    line_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def db_path() -> Path:
    path = settings.db_file
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path(), timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(complaints)")}
    if "state" not in columns:
        conn.execute("ALTER TABLE complaints ADD COLUMN state TEXT NOT NULL DEFAULT ''")


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)


def reset_complaints() -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM complaints")


def prune_old_complaints(*, retention_days: int | None = None) -> int:
    days = retention_days if retention_days is not None else settings.retention_days
    if days <= 0:
        return 0
    cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """
            DELETE FROM complaints
            WHERE COALESCE(NULLIF(created_at, ''), inserted_at) < ?
            """,
            (cutoff,),
        )
        return int(cur.rowcount or 0)


def upsert_complaints(rows: list[ComplaintSchema]) -> int:
    if not rows:
        return 0
    init_db()
    payload = [
        (
            row.source_platform,
            row.post_id,
            row.url,
            row.author_handle,
            row.created_at,
            row.raw_text,
            row.normalized_text,
            row.detected_language_mix,
            row.category,
            row.subcategory,
            row.entity,
            row.location,
            row.state,
            row.severity,
            row.confidence,
            row.engagement,
            row.cluster_id,
        )
        for row in rows
    ]
    with connect() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO complaints (
                source_platform, post_id, url, author_handle, created_at, raw_text,
                normalized_text, detected_language_mix, category, subcategory,
                entity, location, state, severity, confidence, engagement, cluster_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    return len(payload)


def fetch_category_counts() -> list[sqlite3.Row]:
    init_db()
    with connect() as conn:
        return list(
            conn.execute(
                """
                SELECT category, source_platform, COUNT(*) AS volume
                FROM complaints
                GROUP BY category, source_platform
                ORDER BY volume DESC
                """
            )
        )


def record_collector_runs(run_id: str, runs: list[dict]) -> None:
    if not runs:
        return
    init_db()
    payload = [
        (
            run_id,
            str(run.get("source", "")),
            str(run.get("started_at", "")),
            str(run.get("finished_at", "")),
            str(run.get("status", "unknown")),
            int(run.get("row_count", 0) or 0),
            float(run.get("duration_seconds", 0) or 0),
            str(run.get("error", ""))[:1000],
        )
        for run in runs
        if run.get("source")
    ]
    with connect() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO collector_runs (
                run_id, source, started_at, finished_at, status,
                row_count, duration_seconds, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
        conn.execute(
            "DELETE FROM collector_runs WHERE finished_at < ?",
            ((datetime.now(UTC) - timedelta(days=30)).isoformat(),),
        )


def latest_collector_runs() -> list[dict]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT cr.run_id, cr.source, cr.started_at, cr.finished_at,
                   cr.status, cr.row_count, cr.duration_seconds, cr.error
            FROM collector_runs AS cr
            JOIN (
                SELECT source, MAX(id) AS latest_id
                FROM collector_runs
                GROUP BY source
            ) AS latest ON latest.latest_id = cr.id
            ORDER BY cr.source
            """
        ).fetchall()
    return [dict(row) for row in rows]


def latest_collector_run(source: str, *, include_paused: bool = True) -> dict | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT run_id, source, started_at, finished_at, status,
                   row_count, duration_seconds, error
            FROM collector_runs
            WHERE source = ?
              AND (? = 1 OR status != 'paused')
            ORDER BY id DESC
            LIMIT 1
            """,
            (source, 1 if include_paused else 0),
        ).fetchone()
    return dict(row) if row else None
