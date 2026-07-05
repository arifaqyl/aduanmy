#!/usr/bin/env python3
"""TrafficMY Threads Terminal — ops console for the primary rider-signal lane.

Usage:
  python scripts/threads_terminal.py              # dashboard
  python scripts/threads_terminal.py status
  python scripts/threads_terminal.py session
  python scripts/threads_terminal.py runs
  python scripts/threads_terminal.py qa [--prod]
  python scripts/threads_terminal.py replay "MRT Kajang delay 25 min"
  python scripts/threads_terminal.py collect [--write]
  python scripts/threads_terminal.py rejects [--prod]
  python scripts/threads_terminal.py health [--prod]
  python scripts/threads_terminal.py interactive
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from app.core.runtime import bootstrap_repo_root
from app.services.threads_terminal_service import (
    explain_rider_gate,
    fetch_remote_health,
    qa_threads_rows,
    recent_threads_complaints,
    recent_threads_runs,
    reject_reason_counts,
    session_panel,
    status_snapshot,
    threads_source_health,
)

SECRETS = Path(r"D:\MyVault\SECRETS.md")
PROD_HEALTH = "https://arifaqyl.me/traffic"
LOCAL_QA_DB = REPO / "output" / "aduanmy_qa.db"


def _load_password() -> str:
    text = SECRETS.read_text(encoding="utf-8")
    match = re.search(r"^-\s*Password:\s*(.+)$", text, re.MULTILINE)
    if not match:
        raise SystemExit("DigitalOcean password not found in D:\\MyVault\\SECRETS.md")
    return match.group(1).strip()


def fetch_prod_db() -> Path:
    import paramiko

    LOCAL_QA_DB.parent.mkdir(parents=True, exist_ok=True)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect("68.183.181.237", username="root", password=_load_password(), timeout=45)
    _, stdout, _ = ssh.exec_command(
        "docker cp trafficmy:/data/aduanmy.db /tmp/aduanmy_qa.db && test -f /tmp/aduanmy_qa.db && echo OK",
        get_pty=True,
    )
    if stdout.channel.recv_exit_status() != 0 or "OK" not in stdout.read().decode(errors="replace"):
        raise SystemExit("failed to copy production database from container")
    sftp = ssh.open_sftp()
    sftp.get("/tmp/aduanmy_qa.db", str(LOCAL_QA_DB))
    sftp.close()
    ssh.close()
    return LOCAL_QA_DB


def _hr(title: str = "") -> None:
    if title:
        print(f"\n=== {title} ===")
    else:
        print()


def _print_session() -> None:
    panel = session_panel()
    _hr("Session")
    print(f"path      {panel['path']}")
    print(f"available {panel['available']}")
    print(f"updated   {panel.get('updated_at') or '—'}")
    print(f"size      {panel.get('size_bytes', 0)} bytes")


def _print_runs() -> None:
    runs = recent_threads_runs()
    _hr("Recent Threads collector runs")
    if not runs:
        print("No collector_runs rows for threads yet.")
        return
    for row in runs:
        err = f"  err={row['error'][:80]}" if row.get("error") else ""
        print(
            f"{row['finished_at']}  {row['status']:7}  rows={row['row_count']:3}  "
            f"{row['duration_seconds']:5.1f}s{err}"
        )


def _print_health(prod: bool) -> None:
    snap = status_snapshot(prod_health_url=PROD_HEALTH if prod else None)
    _hr("Threads health")
    sess = snap["session"]
    print(f"session: {'OK' if sess.get('available') else 'MISSING'}  updated={sess.get('updated_at') or '—'}")
    col = snap.get("threads_collector") or {}
    if col:
        flag = " NEEDS ATTENTION" if col.get("needs_attention") else ""
        print(
            f"last run: {col.get('finished_at')}  status={col.get('status')}  "
            f"rows={col.get('row_count')}  empty_streak={col.get('consecutive_empty_runs')}{flag}"
        )
        if col.get("error"):
            print(f"error: {col['error']}")
    diag = snap.get("last_diagnostics") or {}
    if diag:
        print(f"last collect diagnostics: {json.dumps(diag, ensure_ascii=False)}")
    if prod:
        remote = snap.get("remote_health")
        if remote:
            threads = next((s for s in remote.get("sources", []) if s.get("source") == "threads"), None)
            print(f"prod health: {remote.get('status')}  threads_rows={remote.get('threads_rows_last_ingest')}")
            if threads:
                print(f"prod threads: empty_streak={threads.get('consecutive_empty_runs')}  err={threads.get('error') or '—'}")
            for alert in remote.get("alerts") or []:
                if "threads" in alert.lower():
                    print(f"ALERT: {alert}")
        elif snap.get("remote_health_error"):
            print(f"prod health fetch failed: {snap['remote_health_error']}")


def _print_status(prod: bool) -> None:
    _print_health(prod)
    _print_runs()
    health = threads_source_health()
    if health and health.get("needs_attention"):
        print("\n⚠ Threads lane degraded — check session or search blockers before trusting quiet board.")


def _print_qa(prod: bool) -> None:
    db_path = fetch_prod_db() if prod else None
    rows = recent_threads_complaints(limit=80, db_path=db_path)
    result = qa_threads_rows(rows)
    _hr("QA simulation" + (" (production DB)" if prod else " (local DB)"))
    print(f"rows={result['total']}  accepted={result['accepted_count']}  rejected={result['rejected_count']}")
    if result["accepted"]:
        print("\nAccepted sample:")
        for item in result["accepted"][:5]:
            print(f"  ✓ {item['created_at']}  {item['entity'] or '—'}  {item['preview'][:100]}")
    if result["rejected"]:
        print("\nRejected sample:")
        for item in result["rejected"][:8]:
            print(f"  ✗ {item.get('reason', '?')}  {item['preview'][:90]}")


def _print_rejects(prod: bool) -> None:
    db_path = fetch_prod_db() if prod else None
    rows = recent_threads_complaints(limit=100, db_path=db_path)
    counts = reject_reason_counts(rows)
    _hr("Reject reason histogram" + (" (prod)" if prod else " (local)"))
    if not counts:
        print("No rejected patterns in sample (or no rows).")
        return
    for reason, count in counts.items():
        print(f"  {count:3}  {reason[:100]}")


def _print_replay(text: str) -> None:
    result = explain_rider_gate(text)
    _hr("Replay gate")
    print(f"accepted: {result['accepted']}")
    print(f"entity:   {result.get('entity') or '—'}")
    print(f"location: {result.get('location') or '—'}")
    print(f"preview:  {result.get('preview')}")
    print("\nSteps:")
    for step in result.get("steps") or []:
        mark = "PASS" if step.get("pass") == "true" else "FAIL"
        print(f"  [{mark}] {step['gate']}: {step['detail']}")


def _cmd_collect(write: bool) -> None:
    from app.collectors.threads.client import collect_threads_sample, get_threads_diagnostics

    _hr("Live collect (may take up to 150s)")
    rows = collect_threads_sample()
    diag = get_threads_diagnostics()
    print(f"accepted_rows={len(rows)}")
    print(f"diagnostics={json.dumps(diag, ensure_ascii=False, indent=2)}")
    for idx, row in enumerate(rows[:8], start=1):
        preview = (row.get("raw_text") or "")[:120].replace("\n", " ")
        print(f"  {idx}. [{row.get('query')}] {preview}")
    if write:
        out = REPO / "output" / "threads_terminal_collect.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"rows": rows, "diagnostics": diag}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote {out}")


def _interactive(prod: bool) -> None:
    menu = """
TrafficMY Threads Terminal
  1 status   2 session   3 runs      4 qa
  5 replay   6 collect   7 health    8 rejects
  q quit
"""
    while True:
        print(menu)
        choice = input("> ").strip().lower()
        if choice in {"q", "quit", "exit"}:
            break
        if choice in {"1", "status"}:
            _print_status(prod)
        elif choice in {"2", "session"}:
            _print_session()
        elif choice in {"3", "runs"}:
            _print_runs()
        elif choice in {"4", "qa"}:
            _print_qa(prod)
        elif choice in {"5", "replay"}:
            text = input("post text: ").strip()
            if text:
                _print_replay(text)
        elif choice in {"6", "collect"}:
            _cmd_collect(write=False)
        elif choice in {"7", "health"}:
            _print_health(prod)
        elif choice in {"8", "rejects"}:
            _print_rejects(prod)
        else:
            print("Unknown command.")


def main() -> None:
    bootstrap_repo_root()
    parser = argparse.ArgumentParser(description="TrafficMY Threads Terminal")
    parser.add_argument("--prod", action="store_true", help="Use production DB / health where applicable")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Dashboard: session + runs + health")
    sub.add_parser("session", help="Threads cookie session status")
    sub.add_parser("runs", help="Recent threads collector_runs")
    sub.add_parser("health", help="Collector + optional prod /api/health")
    sub.add_parser("interactive", help="Interactive menu")

    qa_p = sub.add_parser("qa", help="Re-run scraper gates on recent threads rows")
    qa_p.add_argument("--prod", action="store_true")

    rej_p = sub.add_parser("rejects", help="Histogram of reject reasons")
    rej_p.add_argument("--prod", action="store_true")

    replay_p = sub.add_parser("replay", help="Run gate pipeline on sample text")
    replay_p.add_argument("text", nargs="+", help="Post text to evaluate")

    collect_p = sub.add_parser("collect", help="Run live collect_threads_sample()")
    collect_p.add_argument("--write", action="store_true", help="Save JSON to output/")

    args = parser.parse_args()
    cmd = args.command or "status"
    prod = bool(getattr(args, "prod", False))

    if cmd == "status":
        _print_status(prod)
    elif cmd == "session":
        _print_session()
    elif cmd == "runs":
        _print_runs()
    elif cmd == "health":
        _print_health(prod)
    elif cmd == "qa":
        _print_qa(prod)
    elif cmd == "rejects":
        _print_rejects(prod)
    elif cmd == "replay":
        _print_replay(" ".join(args.text))
    elif cmd == "collect":
        _cmd_collect(getattr(args, "write", False))
    elif cmd == "interactive":
        _interactive(prod)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
