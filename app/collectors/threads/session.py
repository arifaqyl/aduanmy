from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

_COOKIE_NAMES = {"sessionid", "csrftoken", "ds_user_id"}
_COOKIE_DOMAINS = ("threads.com", "threads.net", "instagram.com")
UTC = timezone.utc


def session_path() -> Path:
    return Path(settings.threads_session_path)


def _valid_cookie(cookie: object) -> bool:
    if not isinstance(cookie, dict):
        return False
    name = cookie.get("name")
    value = cookie.get("value")
    domain = str(cookie.get("domain") or "").lower().lstrip(".")
    return bool(
        name in _COOKIE_NAMES
        and isinstance(value, str)
        and value
        and any(domain == allowed or domain.endswith(f".{allowed}") for allowed in _COOKIE_DOMAINS)
    )


def load_storage_state() -> dict | None:
    path = session_path()
    if not path.is_file() or path.stat().st_size > 1_000_000:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    cookies = [cookie for cookie in payload.get("cookies", []) if _valid_cookie(cookie)]
    names = {cookie["name"] for cookie in cookies}
    if not {"sessionid", "csrftoken"}.issubset(names):
        return None
    return {"cookies": cookies, "origins": []}


def save_storage_state(payload: dict) -> None:
    cookies = [cookie for cookie in payload.get("cookies", []) if _valid_cookie(cookie)]
    names = {cookie["name"] for cookie in cookies}
    if not {"sessionid", "csrftoken"}.issubset(names):
        return
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    data = json.dumps({"cookies": cookies, "origins": []}, separators=(",", ":"))
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(data)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(path)
    path.chmod(0o600)


def session_status() -> dict:
    path = session_path()
    available = load_storage_state() is not None
    updated_at = None
    if available:
        updated_at = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    return {"available": available, "updated_at": updated_at}
