from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import settings
from app.core.files import data_dir
from app.db.session import db_path


def backup_database() -> dict:
    """Create a consistent SQLite backup and rotate old copies."""
    source = db_path()
    if not source.exists():
        return {"status": "skipped", "reason": "database_missing"}

    backup_dir = data_dir() / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = backup_dir / f"trafficmy-{stamp}.db"

    src = sqlite3.connect(source, timeout=30.0)
    dst = sqlite3.connect(destination)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    backups = sorted(
        backup_dir.glob("trafficmy-*.db"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    keep = max(1, int(settings.backup_retention_count))
    for old in backups[keep:]:
        old.unlink(missing_ok=True)

    return {
        "status": "ok",
        "path": str(destination),
        "size_bytes": destination.stat().st_size,
        "retained": min(len(backups), keep),
    }
