from __future__ import annotations

import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_test_db(tmp_path, monkeypatch):
    from app.core.config import settings

    original_db_path = settings.db_path
    original_data_dir = settings.data_dir
    original_auto_refresh = settings.auto_refresh_enabled
    original_refresh_on_startup = settings.refresh_on_startup
    original_discovery_depth = settings.discovery_depth
    original_threads_session_path = settings.threads_session_path
    settings.db_path = str(tmp_path / "test_aduanmy.db")
    settings.data_dir = str(tmp_path / "data")
    settings.auto_refresh_enabled = False
    settings.refresh_on_startup = False
    settings.discovery_depth = "minimal"
    settings.threads_session_path = str(tmp_path / "data" / "private" / "threads-session.json")
    try:
        yield
    finally:
        settings.db_path = original_db_path
        settings.data_dir = original_data_dir
        settings.auto_refresh_enabled = original_auto_refresh
        settings.refresh_on_startup = original_refresh_on_startup
        settings.discovery_depth = original_discovery_depth
        settings.threads_session_path = original_threads_session_path
