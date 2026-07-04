"""Delete transport rows on production that fail the live rider-signal gate."""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

import paramiko

from app.pipeline.extract import transport_incident_signal_ok, transport_rider_signal_worthwhile

SECRETS = Path(r"D:\MyVault\SECRETS.md")
LOCAL_DB = Path(r"D:\aduanmy\output\aduanmy_qa.db")


def load_password() -> str:
    text = SECRETS.read_text(encoding="utf-8")
    match = re.search(r"^-\s*Password:\s*(.+)$", text, re.MULTILINE)
    if not match:
        raise SystemExit("password not found")
    return match.group(1).strip()


def pull_db() -> None:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("68.183.181.237", username="root", password=load_password(), timeout=45)
    _, stdout, _ = ssh.exec_command(
        "docker cp trafficmy:/data/aduanmy.db /tmp/aduanmy_qa.db && test -f /tmp/aduanmy_qa.db && echo OK",
        get_pty=True,
    )
    if stdout.channel.recv_exit_status() != 0 or "OK" not in stdout.read().decode(errors="replace"):
        raise SystemExit("failed to copy production database")
    sftp = ssh.open_sftp()
    LOCAL_DB.parent.mkdir(parents=True, exist_ok=True)
    sftp.get("/tmp/aduanmy_qa.db", str(LOCAL_DB))
    sftp.close()
    ssh.close()


def rejected_ids() -> list[int]:
    conn = sqlite3.connect(LOCAL_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, source_platform, raw_text, entity, category
        FROM complaints
        WHERE category = 'transport'
          AND source_platform IN ('threads', 'reddit', 'rss', 'x', 'gtfs_rt')
        """
    ).fetchall()
    conn.close()
    out: list[int] = []
    for row in rows:
        text = row["raw_text"] or ""
        entity = row["entity"] or ""
        source = row["source_platform"]
        if source == "gtfs_rt":
            out.append(int(row["id"]))
            continue
        if not transport_incident_signal_ok(text, entity):
            out.append(int(row["id"]))
            continue
        if not transport_rider_signal_worthwhile(text, entity):
            out.append(int(row["id"]))
    return out


def delete_ids(ids: list[int]) -> int:
    if not ids:
        return 0
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("68.183.181.237", username="root", password=load_password(), timeout=45)
    chunk_size = 80
    deleted = 0
    for i in range(0, len(ids), chunk_size):
        chunk = ids[i : i + chunk_size]
        id_list = ",".join(str(x) for x in chunk)
        py = (
            "import sqlite3; c=sqlite3.connect('/data/aduanmy.db'); "
            f"cur=c.execute('DELETE FROM complaints WHERE id IN ({id_list})'); "
            "print(cur.rowcount); c.commit()"
        )
        cmd = f"docker exec trafficmy python -c \"{py}\""
        _, stdout, stderr = ssh.exec_command(cmd, get_pty=True)
        out = stdout.read().decode(errors="replace").strip()
        err = stderr.read().decode(errors="replace").strip()
        if err:
            print(err, file=sys.stderr)
        deleted += int(out or 0)
    ssh.close()
    return deleted


def main() -> None:
    pull_db()
    ids = rejected_ids()
    deleted = delete_ids(ids)
    print(f"rejected={len(ids)} deleted={deleted}")


if __name__ == "__main__":
    main()
