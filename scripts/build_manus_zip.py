#!/usr/bin/env python3
"""Build TrafficMY Manus revamp handoff zip."""
from __future__ import annotations

import shutil
import zipfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG = REPO / "exports" / "manus-revamp"
OUT = REPO / "exports" / f"trafficmy-manus-revamp-{date.today().isoformat()}.zip"
VAULT_COPY = Path(r"D:\MyVault\Projects\trafficmy-manus-revamp.zip")


def main() -> None:
    frontend_dst = PKG / "frontend"
    if frontend_dst.exists():
        shutil.rmtree(frontend_dst)
    shutil.copytree(REPO / "static", frontend_dst)

    for name in ("PRODUCT.md", "DESIGN.md"):
        src = REPO / name
        if src.is_file():
            shutil.copy2(src, PKG / name)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(PKG.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(PKG.parent).as_posix())

    shutil.copy2(OUT, VAULT_COPY)
    size_mb = OUT.stat().st_size / (1024 * 1024)
    print(f"Created: {OUT}")
    print(f"Copy:    {VAULT_COPY}")
    print(f"Size:    {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
