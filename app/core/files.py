from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

import yaml

from app.core.config import settings


def project_root() -> Path:
    env_root = os.getenv("ADUANMY_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root)

    here = Path(__file__).resolve()
    candidates = [
        Path("/app"),
        here.parents[2],
        here.parents[3] if len(here.parents) > 3 else here.parents[2],
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "configs").is_dir():
            return candidate
    return here.parents[2]


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


def write_json_atomic(path: Path, payload: Any) -> None:
    """Replace a JSON snapshot atomically so readers never see partial files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)
