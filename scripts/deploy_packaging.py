"""Deploy tarball packaging rules (no paramiko import)."""
from __future__ import annotations

from pathlib import Path

# Directory names skipped anywhere in the tree (build/cache artifacts).
SKIP_DIRS_ANYWHERE = {
    ".cursor",
    ".deepsec",
    ".git",
    ".playwright-cli",
    ".pytest_cache",
    ".stitch-incoming",
    "__pycache__",
    ".venv",
    "node_modules",
}
# Directory names skipped only at the repo root — e.g. "data" is the runtime SQLite/GTFS
# volume, but static/data/ holds real product assets (rail-lines.json, etc.) and must ship.
SKIP_DIRS_AT_ROOT = {"data", "output"}
SKIP_FILES = {".env", ".env.production", ".env.local"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
SKIP_DIR_PREFIXES = (".pytest_", ".pytest-", ".tmp-pytest")


def should_skip(path: Path) -> bool:
    if path.parts and path.parts[0] in SKIP_DIRS_AT_ROOT:
        return True
    if any(part in SKIP_DIRS_ANYWHERE or part.startswith(SKIP_DIR_PREFIXES) for part in path.parts):
        return True
    return path.name in SKIP_FILES or path.suffix in SKIP_SUFFIXES
