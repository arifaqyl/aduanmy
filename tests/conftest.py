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
    settings.db_path = str(tmp_path / "test_aduanmy.db")
    settings.data_dir = str(tmp_path / "data")
    try:
        yield
    finally:
        settings.db_path = original_db_path
        settings.data_dir = original_data_dir
