from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.core.config import settings


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def config_path(name: str) -> Path:
    return project_root() / "configs" / name


def load_yaml(name: str) -> dict[str, Any]:
    with config_path(name).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def data_dir() -> Path:
    path = Path(settings.data_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def report_path(name: str) -> Path:
    path = data_dir() / "reports" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def raw_path(name: str) -> Path:
    path = data_dir() / "raw" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

