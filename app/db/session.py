from __future__ import annotations

import sqlite3
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
    severity TEXT NOT NULL,
    confidence REAL NOT NULL,
    engagement TEXT NOT NULL,
    cluster_id TEXT NOT NULL,
    inserted_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_platform, post_id)
);
"""


def db_path() -> Path:
    path = settings.db_file
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA_SQL)


def reset_complaints() -> None:
    init_db()
    with connect() as conn:
        conn.execute("DELETE FROM complaints")


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
                entity, location, severity, confidence, engagement, cluster_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
