from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

from app.db.session import connect, init_db

GTFS_SCHEMA = """
CREATE TABLE IF NOT EXISTS gtfs_routes (
    network TEXT NOT NULL,
    route_id TEXT NOT NULL,
    route_short_name TEXT NOT NULL,
    route_long_name TEXT NOT NULL,
    route_type INTEGER NOT NULL DEFAULT 3,
    trip_count INTEGER NOT NULL DEFAULT 0,
    mode TEXT NOT NULL DEFAULT 'bus',
    state TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (network, route_id)
);
CREATE INDEX IF NOT EXISTS idx_gtfs_routes_short ON gtfs_routes(network, route_short_name);
"""


def init_gtfs_db() -> None:
    init_db()
    with connect() as conn:
        conn.executescript(GTFS_SCHEMA)


def upsert_routes(rows: list[dict]) -> int:
    if not rows:
        return 0
    init_gtfs_db()
    now = datetime.now(UTC).isoformat()
    payload = [
        (
            row["network"],
            row["route_id"],
            row["route_short_name"],
            row["route_long_name"],
            row.get("route_type", 3),
            row.get("trip_count", 0),
            row.get("mode", "bus"),
            row.get("state", ""),
            now,
        )
        for row in rows
    ]
    with connect() as conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO gtfs_routes (
                network, route_id, route_short_name, route_long_name,
                route_type, trip_count, mode, state, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            payload,
        )
    return len(payload)


def lookup_route_short_name(network: str, short_name: str) -> dict | None:
    init_gtfs_db()
    with connect() as conn:
        row = conn.execute(
            """
            SELECT network, route_id, route_short_name, route_long_name, mode, state
            FROM gtfs_routes
            WHERE network = ? AND route_short_name = ?
            LIMIT 1
            """,
            (network, short_name),
        ).fetchone()
    return dict(row) if row else None


def top_routes_by_trips(network: str, *, limit: int = 30) -> list[dict]:
    init_gtfs_db()
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT network, route_id, route_short_name, route_long_name, trip_count, mode, state
            FROM gtfs_routes
            WHERE network = ?
            ORDER BY trip_count DESC
            LIMIT ?
            """,
            (network, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def all_short_names() -> set[str]:
    init_gtfs_db()
    with connect() as conn:
        rows = conn.execute("SELECT DISTINCT route_short_name FROM gtfs_routes").fetchall()
    return {row["route_short_name"] for row in rows if row["route_short_name"]}
