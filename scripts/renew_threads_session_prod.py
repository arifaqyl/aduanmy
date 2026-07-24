#!/usr/bin/env python3
"""Upload TrafficMY threads session to prod (no ingest)."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import paramiko

REPO = Path(r"D:\aduanmy")
LOCAL_SESSION = REPO / "data" / "private" / "threads-session.json"
SECRETS = Path(r"D:\MyVault\SECRETS.md")
THREADTERM = Path(os.path.expanduser(r"~/.threadterm/config.json"))


def build_and_save() -> dict:
    cfg = json.loads(THREADTERM.read_text(encoding="utf-8"))
    s = cfg.get("session") or {}
    if not s.get("sessionid") or not s.get("csrftoken"):
        raise SystemExit("missing cookies — run threadterm login first")
    cookies = []
    for name, http_only in [
        ("sessionid", True),
        ("csrftoken", False),
        ("ds_user_id", False),
        ("mid", False),
        ("ig_did", False),
    ]:
        value = s.get(name)
        if not value:
            continue
        for domain in (".threads.com", ".instagram.com"):
            cookies.append(
                {
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": "/",
                    "expires": -1,
                    "httpOnly": http_only,
                    "secure": True,
                    "sameSite": "Lax",
                }
            )
    state = {"cookies": cookies, "origins": []}
    LOCAL_SESSION.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_SESSION.write_text(json.dumps(state, separators=(",", ":")), encoding="utf-8")
    print(f"local ok ({len(cookies)} cookies)")
    return state


def upload(state: dict) -> None:
    pw = re.search(r"^-\s*Password:\s*(.+)$", SECRETS.read_text(encoding="utf-8"), re.M).group(1).strip()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("68.183.181.237", username="root", password=pw, timeout=45)
    sftp = ssh.open_sftp()
    remote_tmp = "/tmp/threads-session.json"
    with sftp.file(remote_tmp, "w") as f:
        f.write(json.dumps(state, separators=(",", ":")))
    sftp.chmod(remote_tmp, 0o600)
    sftp.close()
    cmd = (
        "install -d -m 700 /var/lib/docker/volumes/trafficmy_data/_data/private && "
        f"install -m 600 {remote_tmp} /var/lib/docker/volumes/trafficmy_data/_data/private/threads-session.json && "
        f"rm -f {remote_tmp} && "
        "stat -c '%y %s' /var/lib/docker/volumes/trafficmy_data/_data/private/threads-session.json"
    )
    _, stdout, stderr = ssh.exec_command(cmd, timeout=60)
    print(stdout.read().decode(errors="replace").strip())
    err = stderr.read().decode(errors="replace").strip()
    code = stdout.channel.recv_exit_status()
    ssh.close()
    if err:
        print(err, file=sys.stderr)
    if code != 0:
        raise SystemExit(code)
    print("prod session installed")


if __name__ == "__main__":
    upload(build_and_save())
