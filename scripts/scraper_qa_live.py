"""Pull transport complaints from production and re-run scraper gates."""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import paramiko

from app.pipeline.extract import (
    extract_bus_route,
    extract_entity,
    transport_incident_signal_ok,
    transport_rider_signal_worthwhile,
)

SECRETS = Path(r"D:\MyVault\SECRETS.md")
OUT = Path(r"D:\aduanmy\output\scraper_qa.json")


def load_password() -> str:
    text = SECRETS.read_text(encoding="utf-8")
    m = re.search(r"^-\s*Password:\s*(.+)$", text, re.MULTILINE)
    if not m:
        raise SystemExit("password not found")
    return m.group(1).strip()


def fetch_rows() -> list[dict]:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("68.183.181.237", username="root", password=load_password(), timeout=45)
    _, stdout, _ = ssh.exec_command(
        "docker cp trafficmy:/data/aduanmy.db /tmp/aduanmy_qa.db && test -f /tmp/aduanmy_qa.db && echo OK",
        get_pty=True,
    )
    if stdout.channel.recv_exit_status() != 0 or "OK" not in stdout.read().decode(errors="replace"):
        raise SystemExit("failed to copy production database from container")
    sftp = ssh.open_sftp()
    local = Path(r"D:\aduanmy\output\aduanmy_qa.db")
    local.parent.mkdir(parents=True, exist_ok=True)
    sftp.get("/tmp/aduanmy_qa.db", str(local))
    sftp.close()
    ssh.close()
    conn = sqlite3.connect(local)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, source_platform, raw_text, entity, location, category, created_at, inserted_at
        FROM complaints
        WHERE category = 'transport'
        ORDER BY COALESCE(created_at, inserted_at) DESC
        LIMIT 120
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def main() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    rows = fetch_rows()
    bad = []
    ok = []
    for row in rows:
        text = row.get("raw_text") or ""
        entity = extract_entity(text, "transport") or row.get("entity") or ""
        incident = transport_incident_signal_ok(text, entity)
        worthwhile = transport_rider_signal_worthwhile(text, entity) if incident else False
        fresh_entity = extract_bus_route(text) or entity
        verdict = {
            "id": row["id"],
            "source": row["source_platform"],
            "entity": row.get("entity"),
            "fresh_entity": fresh_entity,
            "created_at": row.get("created_at"),
            "incident_ok": incident,
            "worthwhile": worthwhile,
            "preview": text[:220].replace("\n", " "),
        }
        if incident and worthwhile:
            ok.append(verdict)
        elif incident:
            bad.append({**verdict, "reason": "incident but not worthwhile"})
        else:
            bad.append({**verdict, "reason": "should not be transport incident"})

    OUT.write_text(json.dumps({"ok_count": len(ok), "bad_count": len(bad), "ok": ok[:15], "bad": bad[:25]}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ok={len(ok)} bad={len(bad)} written {OUT}")


if __name__ == "__main__":
    main()
