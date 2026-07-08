#!/usr/bin/env python3
"""Bundle Threads Terminal into a self-contained zip for handoff / vault."""
from __future__ import annotations

import shutil
import zipfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EXPORTS = REPO / "exports"
VAULT = Path(r"D:\MyVault\Projects")
TODAY = date.today().isoformat()

FILES = [
    ("scripts/threads_terminal.py", "threads-terminal/scripts/threads_terminal.py"),
    ("scripts/threads_terminal_web.py", "threads-terminal/scripts/threads_terminal_web.py"),
    ("scripts/eval_harness.py", "threads-terminal/scripts/eval_harness.py"),
    ("scripts/prune_prod_rejected.py", "threads-terminal/scripts/prune_prod_rejected.py"),
    ("app/services/threads_terminal_service.py", "threads-terminal/app/services/threads_terminal_service.py"),
    ("app/pipeline/extract.py", "threads-terminal/app/pipeline/extract.py"),
    ("app/collectors/threads/client.py", "threads-terminal/app/collectors/threads/client.py"),
    ("app/collectors/threads/session.py", "threads-terminal/app/collectors/threads/session.py"),
    ("tests/test_threads_terminal.py", "threads-terminal/tests/test_threads_terminal.py"),
    ("tests/eval/rider_signal_cases.json", "threads-terminal/tests/eval/rider_signal_cases.json"),
    ("docs/THREADS_TERMINAL.md", "threads-terminal/docs/THREADS_TERMINAL.md"),
]

README = """# TrafficMY Threads Terminal — Full Package

Ops console for the Meta Threads rider-signal lane.

## What's inside

- Rich CLI: `scripts/threads_terminal.py`
- Local web UI: `scripts/threads_terminal_web.py` (port 8005)
- Service layer + sacred gates (`extract.py`)
- Eval harness + labelled cases
- Docs: `docs/THREADS_TERMINAL.md`

## Use inside the full repo (recommended)

This zip is a **reference / handoff pack**. Run commands from the full `aduanmy` repo:

```bash
cd D:\\aduanmy
pip install -e ".[dev]"
python scripts/threads_terminal.py dashboard --prod
python scripts/threads_terminal_web.py
```

## Trust

Do not loosen gates without adding eval cases first.
Never commit secrets or `threads-session.json`.
"""


def main() -> None:
    EXPORTS.mkdir(parents=True, exist_ok=True)
    out = EXPORTS / f"trafficmy-threads-terminal-{TODAY}.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("threads-terminal/README.md", README)
        for src, dest in FILES:
            path = REPO / src
            if not path.is_file():
                raise SystemExit(f"missing: {src}")
            zf.write(path, dest)
    vault = VAULT / "trafficmy-threads-terminal.zip"
    if VAULT.is_dir():
        shutil.copy2(out, vault)
        print(f"vault -> {vault}")
    print(f"wrote -> {out}")
    print(f"files -> {len(FILES) + 1}")


if __name__ == "__main__":
    main()
