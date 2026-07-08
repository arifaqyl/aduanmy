from __future__ import annotations

"""Saved-commute alerts over Telegram.

A rider messages the bot `/watch kelana-jaya` and gets pinged (via the
Telegram Bot API's sendMessage) when that line's status changes to delay
or disruption on a later refresh. This module is intentionally simple:
SQLite for subscriptions + a one-row-per-line "last known status" snapshot
so we only fire on a *transition*, not on every refresh while a line stays
degraded.

Wiring, once ADUANMY_TELEGRAM_BOT_TOKEN is set:
  1. `check_and_notify()` is called at the end of every full ingest
     (see scheduler_service.run_full_now) — safe to call even with no token
     set, it just becomes a no-op.
  2. Point the bot's webhook at POST /api/telegram/webhook (see
     app/api/routes/telegram.py) so `/watch`, `/stop` and `/status` work.

Not yet wired: rate limiting per chat, multi-language replies, unsubscribe-all.
"""

import logging

import requests

from app.core.config import settings
from app.db.session import connect, init_db

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"
ALERT_STATUSES = {"delay", "disruption"}


def _enabled() -> bool:
    return bool(settings.telegram_bot_token)


def send_message(chat_id: str, text: str) -> bool:
    """Low-level send. Returns False (and logs) instead of raising, so a
    Telegram outage never takes down ingest or the webhook route."""
    if not _enabled():
        logger.debug("telegram alerts disabled — skipping send to %s", chat_id)
        return False
    url = TELEGRAM_API.format(token=settings.telegram_bot_token, method="sendMessage")
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.warning("telegram sendMessage failed for %s: %s", chat_id, exc)
        return False


def subscribe(chat_id: str, line_id: str) -> None:
    init_db()
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO telegram_subscriptions (chat_id, line_id) VALUES (?, ?)",
            (str(chat_id), line_id),
        )


def unsubscribe(chat_id: str, line_id: str | None = None) -> int:
    """Remove one subscription, or all of a chat's subscriptions if
    line_id is None (used by /stop)."""
    init_db()
    with connect() as conn:
        if line_id is None:
            cur = conn.execute("DELETE FROM telegram_subscriptions WHERE chat_id = ?", (str(chat_id),))
        else:
            cur = conn.execute(
                "DELETE FROM telegram_subscriptions WHERE chat_id = ? AND line_id = ?",
                (str(chat_id), line_id),
            )
        return int(cur.rowcount or 0)


def subscriptions_for_chat(chat_id: str) -> list[str]:
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT line_id FROM telegram_subscriptions WHERE chat_id = ? ORDER BY line_id",
            (str(chat_id),),
        ).fetchall()
    return [row["line_id"] for row in rows]


def _subscribers_for_line(conn, line_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT chat_id FROM telegram_subscriptions WHERE line_id = ?",
        (line_id,),
    ).fetchall()
    return [row["chat_id"] for row in rows]


def check_and_notify() -> dict:
    """Diff current line statuses against the last snapshot and notify
    subscribers of any line that just transitioned into delay/disruption.
    Safe no-op if the bot token isn't configured. Never raises — a bad
    diff pass should not take down the ingest cycle that calls it."""
    if not _enabled():
        return {"sent": 0, "skipped": "no_token"}

    from app.services.line_status_service import get_line_status_board

    sent = 0
    try:
        board = get_line_status_board()
        lines = board.get("lines", []) if isinstance(board, dict) else board
        init_db()
        with connect() as conn:
            previous = {
                row["line_id"]: row["status"]
                for row in conn.execute("SELECT line_id, status FROM line_status_snapshots").fetchall()
            }
            for line in lines or []:
                line_id = line.get("id") or line.get("line_id")
                status = line.get("status", "unknown")
                if not line_id:
                    continue
                was = previous.get(line_id)
                if status in ALERT_STATUSES and was not in ALERT_STATUSES:
                    for chat_id in _subscribers_for_line(conn, line_id):
                        name = line.get("name", line_id)
                        if send_message(
                            chat_id,
                            f"<b>{name}</b> just changed to <b>{status}</b>. "
                            f"Check trafficmy.arifaqyl.me for rider reports.",
                        ):
                            sent += 1
                conn.execute(
                    """
                    INSERT INTO line_status_snapshots (line_id, status, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(line_id) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at
                    """,
                    (line_id, status),
                )
    except Exception:  # pragma: no cover - defensive, never break ingest
        logger.exception("telegram check_and_notify failed")
        return {"sent": sent, "error": True}
    return {"sent": sent}
