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


def check_source_health_and_alert() -> dict:
    """Page the owner when a collector goes quiet, and again when it recovers.

    This exists because TrafficMY can fail silently in the worst possible way:
    every collector returns zero rows, no exception is raised, and the board
    renders a clean "no rider reports today" that is indistinguishable from a
    genuinely quiet day. That state went unnoticed for two months.

    Fires only on a transition, using source_health_alerts as the last-known
    state, so a collector that stays broken pages once rather than every
    15-minute ingest. Never raises: an alerting failure must not break ingest.
    """
    if not _enabled() or not settings.telegram_ops_chat_id:
        return {"sent": 0, "skipped": "no_token_or_ops_chat"}

    from app.services.source_health_service import get_source_health

    chat = settings.telegram_ops_chat_id
    sent = 0
    transitions: list[dict] = []
    try:
        health = get_source_health()
        init_db()
        with connect() as conn:
            previous = {
                row["source"]: bool(row["needs_attention"])
                for row in conn.execute(
                    "SELECT source, needs_attention FROM source_health_alerts"
                ).fetchall()
            }
            for item in health:
                source = item.get("source")
                if not source:
                    continue
                now_bad = bool(item.get("needs_attention"))
                was_bad = previous.get(source)

                if was_bad is not None and now_bad == was_bad:
                    continue  # no change — stay quiet

                if now_bad:
                    empties = item.get("consecutive_empty_runs", 0)
                    last_ok = item.get("last_nonempty_at") or "never"
                    text = (
                        f"⚠️ <b>TrafficMY collector down</b>\n\n"
                        f"<b>{source}</b> has returned nothing for "
                        f"<b>{empties}</b> consecutive runs.\n"
                        f"Last row: {last_ok}\n\n"
                        f"The board is showing 'no rider reports' — which right now "
                        f"means the collector is broken, not that lines are quiet."
                    )
                elif was_bad:
                    text = f"✅ <b>TrafficMY</b>: <b>{source}</b> is returning rows again."
                else:
                    text = ""

                if text and send_message(chat, text):
                    sent += 1
                transitions.append({"source": source, "needs_attention": now_bad})

                conn.execute(
                    """
                    INSERT INTO source_health_alerts (source, needs_attention, alerted_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(source) DO UPDATE SET
                        needs_attention = excluded.needs_attention,
                        alerted_at = excluded.alerted_at
                    """,
                    (source, 1 if now_bad else 0),
                )
    except Exception:  # pragma: no cover - defensive, never break ingest
        logger.exception("source health alert failed")
        return {"sent": sent, "error": True}
    return {"sent": sent, "transitions": transitions}


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
