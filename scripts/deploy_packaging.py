"""Deploy tarball packaging rules (no paramiko import)."""
from __future__ import annotations

from pathlib import Path

SKIP_DIRS = {
    ".cursor",
    ".deepsec",
    ".git",
    ".playwright-cli",
    ".pytest_cache",
    "__pycache__",
    ".venv",
    "data",
    "node_modules",
    "output",
}
SKIP_FILES = {".env", ".env.production", ".env.local"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
SKIP_DIR_PREFIXES = (".pytest_", ".pytest-", ".tmp-pytest")


def should_skip(path: Path) -> bool:
    if any(part in SKIP_DIRS or part.startswith(SKIP_DIR_PREFIXES) for part in path.parts):
        return True
    return path.name in SKIP_FILES or path.suffix in SKIP_SUFFIXES
