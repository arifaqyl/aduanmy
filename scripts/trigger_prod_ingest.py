"""Run one ingest cycle inside the production TrafficMY container."""
from __future__ import annotations

import json
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
        "'import datetime as _dt; "
        "_dt.UTC = getattr(_dt, \"UTC\", _dt.timezone.utc); "
        "from app.services.ingest_service import run_ingest; "
        "import json; print(json.dumps(run_ingest(respect_cadence=False)))'"
    )
    _, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    ssh.close()
    if err.strip():
        print(err, file=sys.stderr)
    print(out)
    if code != 0:
        raise SystemExit(code)


if __name__ == "__main__":
    main()
