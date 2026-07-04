"""Prune stale transport rows on production (gtfs_rt + rejected social)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import paramiko

SECRETS = Path(r"D:\MyVault\SECRETS.md")


def main() -> None:
    text = SECRETS.read_text(encoding="utf-8")
    match = re.search(r"^-\s*Password:\s*(.+)$", text, re.MULTILINE)
    if not match:
        raise SystemExit("password not found in SECRETS.md")
    password = match.group(1).strip()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("68.183.181.237", username="root", password=password, timeout=45)
    cmd = (
        "docker exec trafficmy python -c "
        "'import sqlite3; c=sqlite3.connect(\"/data/aduanmy.db\"); "
        "cur=c.execute(\"DELETE FROM complaints WHERE source_platform=?\", (\"gtfs_rt\",)); "
        "print(cur.rowcount); c.commit()'"
    )
    _, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    out = stdout.read().decode(errors="replace").strip()
    err = stderr.read().decode(errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    ssh.close()
    if err:
        print(err, file=sys.stderr)
    print(f"gtfs_rt deleted: {out}")
    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
