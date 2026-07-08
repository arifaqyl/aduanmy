#!/usr/bin/env python3
"""TrafficMY Threads Terminal v2 — ops console for the primary rider-signal lane.

Usage:
  python scripts/threads_terminal.py                   # dashboard (local)
  python scripts/threads_terminal.py dashboard [--prod]
  python scripts/threads_terminal.py session
  python scripts/threads_terminal.py runs
  python scripts/threads_terminal.py qa [--prod]
  python scripts/threads_terminal.py replay "MRT Kajang delay 25 min"
  python scripts/threads_terminal.py collect [--write]
  python scripts/threads_terminal.py rejects [--prod]
  python scripts/threads_terminal.py health [--prod]
  python scripts/threads_terminal.py case add "<text>" --reject [--note "reason"]
  python scripts/threads_terminal.py case run
  python scripts/threads_terminal.py impact [--prod]
  python scripts/threads_terminal.py prune [--prod] [--dry-run]
  python scripts/threads_terminal.py export [--prod]
  python scripts/threads_terminal.py interactive [--prod]
  python scripts/threads_terminal_web.py [--prod]   # local web UI :8005

Exit codes: 0 = healthy, 1 = degraded/failures (for scripting).
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

# Force UTF-8 on Windows to avoid cp1252 crashes with Unicode symbols
import os
if os.name == "nt":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Rich imports — graceful fallback if missing
try:
    from rich.align import Align
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text
    from rich.theme import Theme

    _THEME = Theme(
        {
            "pass": "bold green",
            "fail": "bold red",
            "warn": "bold yellow",
            "dim": "dim",
            "header": "bold cyan",
            "entity": "bold magenta",
            "ok": "green",
            "bad": "red",
        }
    )
    console = Console(theme=_THEME)
    RICH = True
except ImportError:
    RICH = False
    console = None  # type: ignore[assignment]
    Align = Rule = None  # type: ignore[assignment,misc]

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

# ── Lazy imports for new service functions ────────────────────────────────────
# These may not exist yet during initial import; load lazily.
_NEW_SERVICE_CACHE: dict = {}


def _svc():
    """Lazy-load new v2 service functions."""
    if _NEW_SERVICE_CACHE:
        return _NEW_SERVICE_CACHE
    from app.services.threads_terminal_service import (
        add_eval_case,
        dashboard_snapshot,
        explain_rider_gate_verbose,
        export_ops_report,
        impact_preview,
        prune_candidates,
        run_eval_cases,
    )

    _NEW_SERVICE_CACHE.update(
        {
            "dashboard_snapshot": dashboard_snapshot,
            "explain_rider_gate_verbose": explain_rider_gate_verbose,
            "add_eval_case": add_eval_case,
            "run_eval_cases": run_eval_cases,
            "impact_preview": impact_preview,
            "prune_candidates": prune_candidates,
            "export_ops_report": export_ops_report,
        }
    )
    return _NEW_SERVICE_CACHE


# ── Prod DB helpers ───────────────────────────────────────────────────────────


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


# ── Rich helpers ──────────────────────────────────────────────────────────────


def _status_icon(ok: bool) -> str:
    return "✓" if ok else "✗"


def _print_plain(msg: str) -> None:
    """Fallback printer when Rich isn't available."""
    print(msg)


def _out(msg: str, style: str = "") -> None:
    if RICH:
        console.print(msg, style=style)
    else:
        _print_plain(msg)


def _run_sparkline(runs: list[dict], width: int = 10) -> str:
    """Return a Rich markup string: last `width` run outcomes as coloured blocks (newest right)."""
    blocks = []
    for r in runs[:width]:
        st = str(r.get("status", "")).lower()
        ok = st in {"completed", "healthy", "ok", "success"}
        blocks.append("[green]█[/green]" if ok else "[red]▄[/red]")
    pad = width - len(blocks)
    return "[dim]" + "░" * pad + "[/dim]" + "".join(reversed(blocks))


# ── Dashboard ─────────────────────────────────────────────────────────────────


def _cmd_dashboard(prod: bool, json_out: bool = False) -> int:
    db_path = fetch_prod_db() if prod else None
    snap = _svc()["dashboard_snapshot"](
        prod_health_url=PROD_HEALTH if prod else None,
        db_path=db_path,
    )

    sess = snap["session"]
    sess_ok = sess.get("available", False)
    col = snap.get("collector") or {}
    col_status = str(col.get("status") or "").lower()
    col_ok = bool(col) and col_status in {"healthy", "completed", "ok", "success"} and not col.get("needs_attention")
    streak = int(col.get("consecutive_empty_runs", 0) or 0)
    runs = snap.get("runs") or []

    if json_out:
        print(json.dumps(snap, ensure_ascii=False, default=str, indent=2))
        degraded = not sess_ok or col.get("needs_attention")
        return 1 if degraded else 0

    if RICH:
        label = "PROD" if prod else "LOCAL"

        # ── Banner ────────────────────────────────────────────────────────────
        console.rule(
            f"[bold cyan]THREADS TERMINAL[/bold cyan]  [dim]v2 · TrafficMY · {label}[/dim]",
            style="dim cyan",
        )

        # ── Status pills row ──────────────────────────────────────────────────
        def _pill(name: str, ok: bool, note: str = "") -> Text:
            t = Text()
            t.append("● " if ok else "○ ", style="bold green" if ok else "bold red")
            t.append(name, style="bold")
            if note:
                t.append(f"  {note}", style="dim")
            return t

        streak_color = "green" if streak == 0 else ("yellow" if streak < 3 else "red")
        streak_t = Text()
        streak_t.append("● " if streak == 0 else "○ ", style=f"bold {streak_color}")
        streak_t.append("STREAK ", style="bold")
        streak_t.append(str(streak), style=f"bold {streak_color}")
        if col.get("needs_attention"):
            streak_t.append("  ⚠ NEEDS ATTENTION", style="bold yellow")

        pills_grid = Table.grid(padding=(0, 4))
        pills_grid.add_column()
        pills_grid.add_column()
        pills_grid.add_column()
        pills_grid.add_row(
            _pill("SESSION", sess_ok, f"updated={str(sess.get('updated_at') or '—')[:16]}"),
            _pill("COLLECTOR", col_ok, col.get("status") or "—"),
            streak_t,
        )
        console.print(Align.center(pills_grid))
        console.print()

        # ── Runs table with sparkline ─────────────────────────────────────────
        spark = _run_sparkline(runs)
        run_table = Table(
            title=f"Recent Runs  {spark}",
            show_lines=False,
            expand=True,
            title_style="header",
        )
        run_table.add_column("Time", style="dim", max_width=20)
        run_table.add_column("Status", max_width=10)
        run_table.add_column("Rows", justify="right", max_width=6)
        run_table.add_column("Duration", justify="right", max_width=8)
        for r in runs[:5]:
            st = str(r.get("status") or "?").lower()
            st_style = "ok" if st in {"healthy", "completed", "ok", "success"} else "bad"
            run_table.add_row(
                str(r.get("finished_at") or "—")[:19],
                Text(r.get("status", "?"), style=st_style),
                str(r.get("row_count", 0)),
                f"{r.get('duration_seconds', 0):.1f}s",
            )
        console.print(run_table)

        # ── Accepted / suspicious samples ─────────────────────────────────────
        acc = snap.get("accepted_sample") or []
        sus = snap.get("suspicious_sample") or []

        if acc:
            acc_lines = "\n".join(
                f"  [ok]✓[/ok] [entity]{item.get('entity') or '—':20}[/entity]"
                f"  [dim]{item.get('preview', '')[:90]}[/dim]"
                for item in acc[:3]
            )
            console.print(Panel(acc_lines, title="Last Accepted", border_style="green"))
        if sus:
            sus_lines = "\n".join(
                f"  [warn]⚠[/warn] [entity]{item.get('entity') or '—':20}[/entity]"
                f"  [dim]{item.get('preview', '')[:90]}[/dim]"
                for item in sus[:3]
            )
            console.print(Panel(sus_lines, title="Suspicious Accepted", border_style="yellow"))

        # ── Remote health ─────────────────────────────────────────────────────
        rh = snap.get("remote_health")
        if rh:
            rh_ok = not rh.get("error") and rh.get("status") not in {None, "error"}
            rh_lines = [
                f"  Prod: status={rh.get('status')}  threads_rows={rh.get('threads_rows_last_ingest')}"
            ]
            for alert in rh.get("alerts") or []:
                if "threads" in alert.lower():
                    rh_lines.append(f"  [warn]ALERT: {alert}[/warn]")
            console.print(Panel(
                "\n".join(rh_lines),
                title="Remote Health",
                border_style="cyan" if rh_ok else "red",
            ))

    else:
        # Plain text fallback
        label = "PROD" if prod else "LOCAL"
        _print_plain(f"=== THREADS TERMINAL v2 ({label}) ===")
        _print_plain(f"SESSION  {'OK' if sess_ok else 'MISSING'}  updated={sess.get('updated_at') or '—'}")
        if col:
            flag = " NEEDS ATTENTION" if col.get("needs_attention") else ""
            _print_plain(
                f"COLLECTOR  status={col.get('status')}  rows={col.get('row_count')}"
                f"  streak={streak}{flag}"
            )
        for r in runs[:5]:
            _print_plain(
                f"  {str(r.get('finished_at') or '—')[:19]}  {r.get('status', '?'):7}"
                f"  rows={r.get('row_count', 0):3}  {r.get('duration_seconds', 0):.1f}s"
            )
        for item in (snap.get("accepted_sample") or [])[:3]:
            _print_plain(f"  ✓ {item.get('entity') or '—'}  {item.get('preview', '')[:90]}")
        for item in (snap.get("suspicious_sample") or [])[:3]:
            _print_plain(f"  ⚠ {item.get('entity') or '—'}  {item.get('preview', '')[:90]}")

    degraded = not sess_ok or col.get("needs_attention")
    return 1 if degraded else 0


# ── Session ───────────────────────────────────────────────────────────────────


def _cmd_session() -> int:
    panel = session_panel()
    if RICH:
        ok = panel.get("available", False)
        t = Table(title="Threads Session", show_header=False, expand=False)
        t.add_column("Key", style="header")
        t.add_column("Value")
        t.add_row("path", str(panel["path"]))
        t.add_row("available", Text(_status_icon(ok), style="ok" if ok else "bad"))
        t.add_row("updated", panel.get("updated_at") or "—")
        t.add_row("size", f"{panel.get('size_bytes', 0)} bytes")
        if ok:
            # Cookie age hint
            updated = panel.get("updated_at")
            if updated:
                from datetime import UTC, datetime

                try:
                    from app.core.freshness import parse_dt

                    dt = parse_dt(updated)
                    if dt:
                        age_h = (datetime.now(UTC) - dt).total_seconds() / 3600
                        hint = "fresh" if age_h < 24 else f"⚠ {age_h:.0f}h old — consider renewal"
                        t.add_row("age", hint)
                except Exception:
                    pass
        console.print(t)
    else:
        _print_plain(f"=== Session ===")
        _print_plain(f"path      {panel['path']}")
        _print_plain(f"available {panel['available']}")
        _print_plain(f"updated   {panel.get('updated_at') or '—'}")
        _print_plain(f"size      {panel.get('size_bytes', 0)} bytes")
    return 0


# ── Runs ──────────────────────────────────────────────────────────────────────


def _cmd_runs() -> int:
    runs = recent_threads_runs()
    if RICH:
        t = Table(title="Recent Threads Collector Runs", expand=True, title_style="header")
        t.add_column("Finished At", style="dim")
        t.add_column("Status")
        t.add_column("Rows", justify="right")
        t.add_column("Duration", justify="right")
        t.add_column("Error")
        if not runs:
            console.print("[dim]No collector_runs rows for threads yet.[/dim]")
            return 0
        for row in runs:
            st = row.get("status", "?")
            st_l = str(st).lower()
            err = (row.get("error") or "")[:80]
            t.add_row(
                str(row.get("finished_at") or "—")[:19],
                Text(st, style="ok" if st_l in {"healthy", "completed", "ok", "success"} else "bad"),
                str(row.get("row_count", 0)),
                f"{row.get('duration_seconds', 0):.1f}s",
                err or "—",
            )
        console.print(t)
    else:
        _print_plain("=== Recent Threads collector runs ===")
        if not runs:
            _print_plain("No collector_runs rows for threads yet.")
            return 0
        for row in runs:
            err = f"  err={row['error'][:80]}" if row.get("error") else ""
            _print_plain(
                f"{row['finished_at']}  {row['status']:7}  rows={row['row_count']:3}  "
                f"{row['duration_seconds']:5.1f}s{err}"
            )
    return 0


# ── Health ────────────────────────────────────────────────────────────────────


def _cmd_health(prod: bool) -> int:
    snap = status_snapshot(prod_health_url=PROD_HEALTH if prod else None)
    exit_code = 0
    if RICH:
        sess = snap["session"]
        sess_ok = sess.get("available", False)
        lines = [f"  Session: {_status_icon(sess_ok)} {'OK' if sess_ok else 'MISSING'}  updated={sess.get('updated_at') or '—'}"]
        col = snap.get("threads_collector") or {}
        if col:
            flag = "  [warn]⚠ NEEDS ATTENTION[/warn]" if col.get("needs_attention") else ""
            lines.append(
                f"  Last run: {col.get('finished_at')}  status={col.get('status')}  "
                f"rows={col.get('row_count')}  empty_streak={col.get('consecutive_empty_runs')}{flag}"
            )
            if col.get("error"):
                lines.append(f"  [bad]Error: {col['error']}[/bad]")
            if col.get("needs_attention") or col.get("status") == "failed":
                exit_code = 1
        if not sess_ok:
            exit_code = 1
        diag = snap.get("last_diagnostics") or {}
        if diag:
            lines.append(f"  Diagnostics: {json.dumps(diag, ensure_ascii=False)[:200]}")
        if prod:
            remote = snap.get("remote_health")
            if remote:
                lines.append(f"  Prod: status={remote.get('status')}  threads_rows={remote.get('threads_rows_last_ingest')}")
                for alert in remote.get("alerts") or []:
                    if "threads" in alert.lower():
                        lines.append(f"  [warn]ALERT: {alert}[/warn]")
            elif snap.get("remote_health_error"):
                lines.append(f"  [bad]Prod health fetch failed: {snap['remote_health_error']}[/bad]")
        console.print(Panel("\n".join(lines), title="Threads Health", border_style="cyan"))
    else:
        sess = snap["session"]
        _print_plain(f"=== Threads health ===")
        _print_plain(f"session: {'OK' if sess.get('available') else 'MISSING'}  updated={sess.get('updated_at') or '—'}")
        col = snap.get("threads_collector") or {}
        if col:
            flag = " NEEDS ATTENTION" if col.get("needs_attention") else ""
            _print_plain(
                f"last run: {col.get('finished_at')}  status={col.get('status')}  "
                f"rows={col.get('row_count')}  empty_streak={col.get('consecutive_empty_runs')}{flag}"
            )
            if col.get("error"):
                _print_plain(f"error: {col['error']}")
        if prod:
            remote = snap.get("remote_health")
            if remote:
                _print_plain(f"prod health: {remote.get('status')}  threads_rows={remote.get('threads_rows_last_ingest')}")
            elif snap.get("remote_health_error"):
                _print_plain(f"prod health fetch failed: {snap['remote_health_error']}")

    health = threads_source_health()
    if health and health.get("needs_attention"):
        _out("⚠ Threads lane degraded — check session or search blockers before trusting quiet board.", style="warn")
        exit_code = 1
    return exit_code


# ── QA ────────────────────────────────────────────────────────────────────────


def _cmd_qa(prod: bool, json_out: bool = False) -> int:
    db_path = fetch_prod_db() if prod else None
    rows = recent_threads_complaints(limit=80, db_path=db_path)
    result = qa_threads_rows(rows)
    label = "production DB" if prod else "local DB"

    if json_out:
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        return 1 if result["rejected_count"] > 0 else 0

    if RICH:
        console.print(
            f"[header]QA simulation ({label})[/header]  "
            f"rows={result['total']}  [ok]accepted={result['accepted_count']}[/ok]  "
            f"[bad]rejected={result['rejected_count']}[/bad]"
        )
        if result["accepted"]:
            t = Table(title="Accepted Sample", expand=True, title_style="ok")
            t.add_column("Date", style="dim", max_width=20)
            t.add_column("Entity", style="entity", max_width=25)
            t.add_column("Preview")
            for item in result["accepted"][:5]:
                t.add_row(
                    str(item.get("created_at") or "—")[:19],
                    item.get("entity") or "—",
                    item.get("preview", "")[:100],
                )
            console.print(t)
        if result["rejected"]:
            t = Table(title="Rejected Sample", expand=True, title_style="bad")
            t.add_column("Reason", max_width=40)
            t.add_column("Preview")
            for item in result["rejected"][:8]:
                t.add_row(
                    item.get("reason", "?"),
                    item.get("preview", "")[:90],
                )
            console.print(t)
    else:
        _print_plain(f"=== QA simulation ({label}) ===")
        _print_plain(f"rows={result['total']}  accepted={result['accepted_count']}  rejected={result['rejected_count']}")
        for item in (result.get("accepted") or [])[:5]:
            _print_plain(f"  ✓ {item.get('created_at', '—')}  {item.get('entity') or '—'}  {item.get('preview', '')[:100]}")
        for item in (result.get("rejected") or [])[:8]:
            _print_plain(f"  ✗ {item.get('reason', '?')}  {item.get('preview', '')[:90]}")

    return 1 if result["rejected_count"] > 0 else 0


# ── Replay ────────────────────────────────────────────────────────────────────


def _cmd_replay(text: str, verbose: bool = True, json_out: bool = False) -> int:
    if verbose:
        try:
            result = _svc()["explain_rider_gate_verbose"](text)
        except Exception:
            result = explain_rider_gate(text)
    else:
        result = explain_rider_gate(text)

    accepted = result.get("accepted", False)

    if json_out:
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        return 0 if accepted else 1

    if RICH:
        title_style = "ok" if accepted else "bad"
        header = f"{'ACCEPTED' if accepted else 'REJECTED'}  entity={result.get('entity') or '—'}  location={result.get('location') or '—'}"
        lines = [f"  [dim]Preview:[/dim] {result.get('preview', '')[:200]}"]
        for step in result.get("steps") or []:
            is_pass = step.get("pass") == "true"
            mark = "[ok]PASS[/ok]" if is_pass else "[bad]FAIL[/bad]"
            lines.append(f"  {mark}  {step['gate']}: {step['detail']}")
            matched = step.get("matched_terms")
            if matched:
                lines.append(f"        [dim]matched: {', '.join(str(m) for m in matched[:10])}[/dim]")
        console.print(Panel("\n".join(lines), title=header, border_style=title_style))
    else:
        _print_plain(f"=== Replay gate ===")
        _print_plain(f"accepted: {accepted}")
        _print_plain(f"entity:   {result.get('entity') or '—'}")
        _print_plain(f"location: {result.get('location') or '—'}")
        _print_plain(f"preview:  {result.get('preview')}")
        for step in result.get("steps") or []:
            mark = "PASS" if step.get("pass") == "true" else "FAIL"
            _print_plain(f"  [{mark}] {step['gate']}: {step['detail']}")
            matched = step.get("matched_terms")
            if matched:
                _print_plain(f"          matched: {', '.join(str(m) for m in matched[:10])}")

    return 0 if accepted else 1


# ── Rejects ───────────────────────────────────────────────────────────────────


def _cmd_rejects(prod: bool) -> int:
    db_path = fetch_prod_db() if prod else None
    rows = recent_threads_complaints(limit=100, db_path=db_path)
    counts = reject_reason_counts(rows)
    label = "prod" if prod else "local"

    if RICH:
        if not counts:
            console.print("[dim]No rejected patterns in sample.[/dim]")
            return 0
        t = Table(title=f"Reject Reason Histogram ({label})", expand=True, title_style="header")
        t.add_column("Count", justify="right", max_width=6)
        t.add_column("Reason")
        for reason, count in counts.items():
            t.add_row(str(count), reason[:100])
        console.print(t)
    else:
        _print_plain(f"=== Reject reason histogram ({label}) ===")
        if not counts:
            _print_plain("No rejected patterns in sample (or no rows).")
            return 0
        for reason, count in counts.items():
            _print_plain(f"  {count:3}  {reason[:100]}")
    return 0


# ── Collect ───────────────────────────────────────────────────────────────────


def _cmd_collect(write: bool) -> int:
    from app.collectors.threads.client import collect_threads_sample, get_threads_diagnostics

    _out("Live collect (may take up to 150s)…", style="header")
    rows = collect_threads_sample()
    diag = get_threads_diagnostics()

    if RICH:
        console.print(f"  [ok]accepted_rows={len(rows)}[/ok]")
        console.print(f"  diagnostics={json.dumps(diag, ensure_ascii=False)[:300]}")
        for idx, row in enumerate(rows[:8], start=1):
            preview = (row.get("raw_text") or "")[:120].replace("\n", " ")
            console.print(f"  {idx}. [dim][{row.get('query')}][/dim] {preview}")
    else:
        _print_plain(f"accepted_rows={len(rows)}")
        _print_plain(f"diagnostics={json.dumps(diag, ensure_ascii=False, indent=2)}")
        for idx, row in enumerate(rows[:8], start=1):
            preview = (row.get("raw_text") or "")[:120].replace("\n", " ")
            _print_plain(f"  {idx}. [{row.get('query')}] {preview}")

    if write:
        out = REPO / "output" / "threads_terminal_collect.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"rows": rows, "diagnostics": diag}, ensure_ascii=False, indent=2), encoding="utf-8")
        _out(f"Wrote {out}", style="ok")
    return 0


# ── Case add / run ────────────────────────────────────────────────────────────


def _cmd_case_add(text: str, expected: bool, note: str = "") -> int:
    result = _svc()["add_eval_case"](text, expected=expected, note=note)
    if result.get("added"):
        _out(f"✓ Added eval case (total={result['total_cases']}). expected={'accept' if expected else 'reject'}", style="ok")
        # Also run replay so operator sees the gate result
        _cmd_replay(text)
        return 0
    else:
        _out(f"✗ Not added: {result.get('reason', 'unknown')}", style="bad")
        return 1


def _cmd_case_run() -> int:
    result = _svc()["run_eval_cases"]()

    if RICH:
        total = result.get("total", 0)
        passed = result.get("passed", 0)
        style = "ok" if passed == total else "bad"
        console.print(
            f"[{style}]{passed}/{total} passed[/{style}]  "
            f"accuracy={result.get('accuracy', 0):.1%}  "
            f"precision={result.get('precision', 0):.1%}  "
            f"recall={result.get('recall', 0):.1%}"
        )
        failures = result.get("failures") or []
        if failures:
            t = Table(title="Failures", expand=True, title_style="bad")
            t.add_column("Type", max_width=15)
            t.add_column("Text")
            t.add_column("Note", style="dim")
            for f in failures:
                kind = "false positive" if f.get("actual") else "false negative"
                t.add_row(kind, f.get("text", "")[:80], f.get("note", ""))
            console.print(t)
    else:
        total = result.get("total", 0)
        passed = result.get("passed", 0)
        _print_plain(
            f"{passed}/{total} passed | accuracy {result.get('accuracy', 0):.1%} | "
            f"precision {result.get('precision', 0):.1%} | recall {result.get('recall', 0):.1%}"
        )
        for f in result.get("failures") or []:
            kind = "false positive" if f.get("actual") else "false negative"
            _print_plain(f"  FAIL ({kind}): {f.get('text', '')[:80]} — note: {f.get('note', '')}")

    return 1 if result.get("failures") else 0


# ── Impact ────────────────────────────────────────────────────────────────────


def _cmd_impact(prod: bool) -> int:
    db_path = fetch_prod_db() if prod else None
    rows = _svc()["impact_preview"](db_path=db_path)

    if RICH:
        if not rows:
            console.print("[dim]No threads transport rows found.[/dim]")
            return 0
        t = Table(title="Board Impact Preview", expand=True, title_style="header")
        t.add_column("Entity", style="entity")
        t.add_column("Total", justify="right")
        t.add_column("Prune", justify="right")
        t.add_column("Keep", justify="right")
        t.add_column("Current", max_width=10)
        t.add_column("Projected", max_width=10)
        for item in rows:
            proj_style = "warn" if item["projected_severity"] != item["current_severity"] else ""
            t.add_row(
                item["entity"] or "—",
                str(item["total_rows"]),
                str(item["would_prune"]),
                str(item["remaining_rows"]),
                item["current_severity"],
                Text(item["projected_severity"], style=proj_style) if proj_style else item["projected_severity"],
            )
        console.print(t)
    else:
        _print_plain("=== Board Impact Preview ===")
        for item in rows:
            _print_plain(
                f"  {item['entity'] or '—':30s}  total={item['total_rows']}  "
                f"prune={item['would_prune']}  keep={item['remaining_rows']}  "
                f"{item['current_severity']} → {item['projected_severity']}"
            )
    return 0


# ── Prune ─────────────────────────────────────────────────────────────────────


def _cmd_prune(prod: bool, dry_run: bool) -> int:
    db_path = fetch_prod_db() if prod else None
    if db_path is None:
        _out("prune requires --prod flag (operates on production DB only)", style="warn")
        return 1

    candidates = _svc()["prune_candidates"](db_path=db_path)

    if RICH:
        if not candidates:
            console.print("[ok]No rows to prune — gates look clean.[/ok]")
            return 0
        t = Table(title=f"Prune Candidates ({'DRY RUN' if dry_run else 'LIVE'})", expand=True, title_style="warn")
        t.add_column("ID", justify="right", max_width=8)
        t.add_column("Entity", style="entity", max_width=25)
        t.add_column("Preview")
        t.add_column("Reason", style="dim")
        for c in candidates[:30]:
            t.add_row(str(c["id"]), c.get("entity") or "—", c.get("preview", "")[:80], c.get("reason", ""))
        console.print(t)
        console.print(f"  Total: [warn]{len(candidates)}[/warn] rows would be deleted")
    else:
        _print_plain(f"=== Prune Candidates ({'DRY RUN' if dry_run else 'LIVE'}) ===")
        for c in candidates[:30]:
            _print_plain(f"  id={c['id']}  {c.get('entity') or '—'}  {c.get('preview', '')[:80]}  [{c.get('reason', '')}]")
        _print_plain(f"Total: {len(candidates)} rows")

    if dry_run:
        return 0

    # Confirm before destructive action
    confirm = input(f"\nDelete {len(candidates)} rows from production? (yes/no): ").strip().lower()
    if confirm != "yes":
        _out("Aborted.", style="dim")
        return 0

    from scripts.prune_prod_rejected import delete_ids

    ids = [c["id"] for c in candidates]
    deleted = delete_ids(ids)
    _out(f"✓ Deleted {deleted} rows from production.", style="ok")
    return 0


# ── Interactive ───────────────────────────────────────────────────────────────

_INTERACTIVE_MENU = """
TrafficMY Threads Terminal v2
─────────────────────────────
  1  dashboard       5  replay         9  case add
  2  session         6  collect       10  case run
  3  runs            7  health        11  impact
  4  qa              8  rejects       12  prune --dry-run
 13  export         14  guided        15  doctor
  q  quit
"""


def _interactive(prod: bool) -> None:
    if RICH:
        console.print(Panel(_INTERACTIVE_MENU.strip(), title="Menu", border_style="cyan"))
    else:
        print(_INTERACTIVE_MENU)

    while True:
        try:
            choice = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if choice in {"q", "quit", "exit"}:
            break
        if choice in {"1", "dashboard"}:
            _cmd_dashboard(prod)
        elif choice in {"2", "session"}:
            _cmd_session()
        elif choice in {"3", "runs"}:
            _cmd_runs()
        elif choice in {"4", "qa"}:
            _cmd_qa(prod)
        elif choice in {"5", "replay"}:
            text = input("post text: ").strip()
            if text:
                _cmd_replay(text)
        elif choice in {"6", "collect"}:
            _cmd_collect(write=False)
        elif choice in {"7", "health"}:
            _cmd_health(prod)
        elif choice in {"8", "rejects"}:
            _cmd_rejects(prod)
        elif choice in {"9", "case add", "case"}:
            text = input("post text: ").strip()
            if not text:
                continue
            verdict = input("expected (accept/reject): ").strip().lower()
            expected = verdict in {"accept", "true", "yes", "1"}
            note = input("note (optional): ").strip()
            _cmd_case_add(text, expected, note)
        elif choice in {"10", "case run", "eval"}:
            _cmd_case_run()
        elif choice in {"11", "impact"}:
            _cmd_impact(prod)
        elif choice in {"12", "prune"}:
            _cmd_prune(prod, dry_run=True)
        elif choice in {"13", "export"}:
            _cmd_export(prod)
        elif choice in {"14", "guided"}:
            _cmd_guided(prod)
        elif choice in {"15", "doctor"}:
            _cmd_doctor()
        else:
            _out("Unknown command. Enter 1-14 or q.", style="dim")

        # Re-show menu hint
        if RICH:
            console.print("[dim]Enter 1-14 or q to quit[/dim]")


# ── Guided workflow ───────────────────────────────────────────────────────────


def _cmd_guided(prod: bool) -> int:
    """Guided QA loop: qa → replay → case add → eval → prune dry-run."""
    _out("=== Guided QA Workflow ===", style="header")
    _out("Step 1: Run QA to find suspicious rows…", style="header")
    _cmd_qa(prod)

    _out("\nStep 2: Replay a suspicious post to see gate details.", style="header")
    text = input("Paste post text to replay (or press Enter to skip): ").strip()
    if text:
        _cmd_replay(text)

        _out("\nStep 3: Add to eval set?", style="header")
        add = input("Add this to eval cases? (y/n): ").strip().lower()
        if add in {"y", "yes"}:
            verdict = input("Should this be accepted or rejected? (accept/reject): ").strip().lower()
            expected = verdict in {"accept", "true", "yes"}
            note = input("Note: ").strip()
            _cmd_case_add(text, expected, note)

    _out("\nStep 4: Run eval harness…", style="header")
    run_eval = input("Run eval now? (y/n): ").strip().lower()
    if run_eval in {"y", "yes"}:
        _cmd_case_run()

    _out("\nStep 5: Preview prune impact…", style="header")
    if prod:
        _cmd_prune(prod, dry_run=True)
    else:
        _out("(Skipped — not in --prod mode)", style="dim")

    _out("\n✓ Guided workflow complete.", style="ok")
    return 0


# ── Watch ─────────────────────────────────────────────────────────────────────


def _cmd_watch(interval: int, prod: bool) -> int:
    """Auto-refresh dashboard every `interval` seconds until Ctrl+C."""
    import time

    if RICH:
        console.print(
            f"[dim]Watching every {interval}s — Ctrl+C to stop[/dim]"
        )
    else:
        _print_plain(f"Watching every {interval}s — Ctrl+C to stop")

    try:
        while True:
            if RICH:
                console.clear()
            _cmd_dashboard(prod)
            if RICH:
                console.rule(
                    f"[dim]next refresh in {interval}s · Ctrl+C to stop[/dim]",
                    style="dim",
                )
            else:
                _print_plain(f"--- next in {interval}s ---")
            time.sleep(interval)
    except KeyboardInterrupt:
        if RICH:
            console.print("\n[dim]Watch stopped.[/dim]")
        else:
            _print_plain("Watch stopped.")
    return 0


# ── Doctor ────────────────────────────────────────────────────────────────────


def _cmd_doctor(json_out: bool = False) -> int:
    """One-shot health checklist: session, last run, eval pass rate, gate self-test."""
    from app.services.threads_terminal_service import doctor_checks

    result = doctor_checks()

    if json_out:
        print(json.dumps(result, ensure_ascii=False, default=str, indent=2))
        return 0 if result["all_ok"] else 1

    if RICH:
        console.rule(
            "[bold cyan]THREADS TERMINAL[/bold cyan]  [dim]— doctor[/dim]",
            style="dim cyan",
        )
        lines = []
        for c in result["checks"]:
            ok = c["ok"]
            icon = "[ok]✓[/ok]" if ok else "[bad]✗[/bad]"
            lines.append(
                f"  {icon}  [bold]{c['name']:<18}[/bold]  [dim]{c['detail']}[/dim]"
            )
        lines.append("")
        if result["all_ok"]:
            lines.append("  [ok]All checks passed.[/ok]")
        else:
            lines.append("  [bad]Some checks FAILED — investigate above.[/bad]")
        border = "cyan" if result["all_ok"] else "red"
        console.print(Panel("\n".join(lines), title="Health Checklist", border_style=border))
    else:
        _print_plain("=== Doctor health checklist ===")
        for c in result["checks"]:
            icon = "✓" if c["ok"] else "✗"
            _print_plain(f"  {icon}  {c['name']:<18}  {c['detail']}")
        _print_plain("")
        _print_plain(
            "All checks passed." if result["all_ok"] else "Some checks FAILED."
        )

    return 0 if result["all_ok"] else 1


# ── Export report ─────────────────────────────────────────────────────────────


def _cmd_export(prod: bool) -> int:
    db_path = fetch_prod_db() if prod else None
    path = _svc()["export_ops_report"](
        prod_health_url=PROD_HEALTH if prod else None,
        db_path=db_path,
    )
    _out(f"✓ Wrote ops report → {path}", style="ok")
    return 0


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    bootstrap_repo_root()
    parser = argparse.ArgumentParser(
        description="TrafficMY Threads Terminal v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--prod", action="store_true", help="Use production DB / health where applicable")
    sub = parser.add_subparsers(dest="command")

    dash_p = sub.add_parser("dashboard", help="One-screen ops dashboard")
    dash_p.add_argument("--prod", action="store_true")
    dash_p.add_argument("--json", action="store_true", dest="json_out", help="Output JSON for piping")
    status_p = sub.add_parser("status", help="Alias for dashboard")
    status_p.add_argument("--prod", action="store_true")
    status_p.add_argument("--json", action="store_true", dest="json_out", help="Output JSON for piping")
    sub.add_parser("session", help="Threads cookie session status")
    sub.add_parser("runs", help="Recent threads collector_runs")
    health_p = sub.add_parser("health", help="Collector + optional prod /api/health")
    health_p.add_argument("--prod", action="store_true")
    inter_p = sub.add_parser("interactive", help="Interactive menu")
    inter_p.add_argument("--prod", action="store_true")

    guided_p = sub.add_parser("guided", help="Guided QA → replay → case add → eval → prune workflow")
    guided_p.add_argument("--prod", action="store_true")

    qa_p = sub.add_parser("qa", help="Re-run scraper gates on recent threads rows")
    qa_p.add_argument("--prod", action="store_true")
    qa_p.add_argument("--json", action="store_true", dest="json_out", help="Output JSON for piping")

    rej_p = sub.add_parser("rejects", help="Histogram of reject reasons")
    rej_p.add_argument("--prod", action="store_true")

    replay_p = sub.add_parser("replay", help="Run gate pipeline on sample text")
    replay_p.add_argument("text", nargs="+", help="Post text to evaluate")
    replay_p.add_argument("--json", action="store_true", dest="json_out", help="Output JSON for piping")

    collect_p = sub.add_parser("collect", help="Run live collect_threads_sample()")
    collect_p.add_argument("--write", action="store_true", help="Save JSON to output/")

    # case subcommand group
    case_p = sub.add_parser("case", help="Eval case management")
    case_sub = case_p.add_subparsers(dest="case_command")

    case_add_p = case_sub.add_parser("add", help="Add a labelled eval case")
    case_add_p.add_argument("text", nargs="+", help="Post text")
    case_add_p.add_argument("--accept", action="store_true", help="Mark as should-accept")
    case_add_p.add_argument("--reject", action="store_true", help="Mark as should-reject")
    case_add_p.add_argument("--note", default="", help="Optional note")

    case_sub.add_parser("run", help="Run eval harness on all cases")

    impact_p = sub.add_parser("impact", help="Board severity impact preview")
    impact_p.add_argument("--prod", action="store_true")

    prune_p = sub.add_parser("prune", help="Prune rejected rows from prod DB")
    prune_p.add_argument("--prod", action="store_true")
    prune_p.add_argument("--dry-run", action="store_true", help="Preview without deleting")

    export_p = sub.add_parser("export", help="Write JSON ops report to output/")
    export_p.add_argument("--prod", action="store_true")

    watch_p = sub.add_parser(
        "watch",
        help="Auto-refresh dashboard every N seconds until Ctrl+C (default 30s)",
    )
    watch_p.add_argument("--interval", type=int, default=30, metavar="SECONDS")
    watch_p.add_argument("--prod", action="store_true")

    doctor_p = sub.add_parser(
        "doctor",
        help="One-shot health checklist: session, last run, eval pass rate, gate self-test",
    )
    doctor_p.add_argument("--json", action="store_true", dest="json_out", help="Output JSON")

    args = parser.parse_args()
    cmd = args.command or "dashboard"
    # Accept --prod on either the root parser or the subcommand.
    prod = bool(getattr(args, "prod", False))
    exit_code = 0

    json_out = bool(getattr(args, "json_out", False))

    if cmd in {"dashboard", "status"}:
        exit_code = _cmd_dashboard(prod, json_out=json_out)
    elif cmd == "session":
        exit_code = _cmd_session()
    elif cmd == "runs":
        exit_code = _cmd_runs()
    elif cmd == "health":
        exit_code = _cmd_health(prod)
    elif cmd == "qa":
        exit_code = _cmd_qa(prod, json_out=json_out)
    elif cmd == "rejects":
        exit_code = _cmd_rejects(prod)
    elif cmd == "replay":
        exit_code = _cmd_replay(" ".join(args.text), json_out=json_out)
    elif cmd == "collect":
        exit_code = _cmd_collect(getattr(args, "write", False))
    elif cmd == "case":
        case_cmd = getattr(args, "case_command", None)
        if case_cmd == "add":
            text = " ".join(args.text)
            if args.accept:
                expected = True
            elif args.reject:
                expected = False
            else:
                print("Error: specify --accept or --reject", file=sys.stderr)
                raise SystemExit(1)
            exit_code = _cmd_case_add(text, expected, args.note)
        elif case_cmd == "run":
            exit_code = _cmd_case_run()
        else:
            case_p.print_help()
    elif cmd == "impact":
        exit_code = _cmd_impact(prod)
    elif cmd == "prune":
        exit_code = _cmd_prune(prod, getattr(args, "dry_run", False))
    elif cmd == "export":
        exit_code = _cmd_export(prod)
    elif cmd == "watch":
        exit_code = _cmd_watch(getattr(args, "interval", 30), prod)
    elif cmd == "doctor":
        exit_code = _cmd_doctor(json_out=json_out)
    elif cmd == "guided":
        exit_code = _cmd_guided(prod)
    elif cmd == "interactive":
        _interactive(prod)
    else:
        parser.print_help()

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
