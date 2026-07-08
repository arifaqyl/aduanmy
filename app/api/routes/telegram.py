from __future__ import annotations

"""Telegram webhook for saved-commute alerts.

Point your bot's webhook at POST /api/telegram/webhook?secret=<ADUANMY_TELEGRAM_WEBHOOK_SECRET>.
Commands (all case-insensitive, line id matches app/core LINE_CATALOG ids
e.g. kelana-jaya, ampang-sri-petaling, putrajaya, kajang, monorail, ktm-komuter):

  /watch <line-id>   subscribe this chat to alerts for that line
  /stop [line-id]    unsubscribe from one line, or all lines if omitted
  /status            list this chat's current subscriptions

Not yet built: inline line-name matching (currently requires the exact
catalog id), rate limiting, and a /watch flow that lists lines as buttons.
"""

from fastapi import APIRouter, HTTPException, Query, Request

from app.core.config import settings
from app.services.telegram_alerts import send_message, subscribe, subscriptions_for_chat, unsubscribe

router = APIRouter()


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request, secret: str = Query(default="")) -> dict:
    if not settings.telegram_bot_token:
        raise HTTPException(status_code=503, detail="Telegram alerts not configured")
    if settings.telegram_webhook_secret and secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=403, detail="Bad webhook secret")

    payload = await request.json()
    message = payload.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return {"ok": True}

    parts = text.split()
    command = parts[0].lower()

    if command == "/watch" and len(parts) > 1:
        line_id = parts[1].lower()
        subscribe(str(chat_id), line_id)
        send_message(str(chat_id), f"Watching <b>{line_id}</b>. You'll get a message when it changes to delay or disruption.")
    elif command == "/stop":
        line_id = parts[1].lower() if len(parts) > 1 else None
        removed = unsubscribe(str(chat_id), line_id)
        send_message(
            str(chat_id),
            "Stopped watching that line." if line_id else f"Stopped all alerts ({removed} removed).",
        )
    elif command == "/status":
        lines = subscriptions_for_chat(str(chat_id))
        send_message(
            str(chat_id),
            "Watching: " + ", ".join(lines) if lines else "You're not watching any lines yet. Try /watch kelana-jaya",
        )
    else:
        send_message(
            str(chat_id),
            "Commands: /watch &lt;line-id&gt;, /stop [line-id], /status",
        )

    return {"ok": True}
