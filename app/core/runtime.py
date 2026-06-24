from __future__ import annotations

import os
from pathlib import Path


def bootstrap_repo_root() -> Path:
    root = Path(__file__).resolve().parents[2]
    os.chdir(root)
    return root

