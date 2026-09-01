"""Reddit read-only OAuth lane.

Why this exists: old.reddit.com now answers HTML scrapes with a login
interstitial. It returns HTTP 200, the parser finds no results, and the
collector reports zero rows without raising — the board went quiet and
nothing said why. The unauthenticated .json endpoints answer 403.

Reddit's application-only OAuth ("client_credentials") is the supported way
to read public listings. It needs a registered app but no user account, no
password, and no scraping, so it does not carry the terms-of-service problem
the Threads lane does.

Register once at https://www.reddit.com/prefs/apps (type: script), then:

    ADUANMY_REDDIT_CLIENT_ID=...
    ADUANMY_REDDIT_CLIENT_SECRET=...

Without those this module reports unconfigured and the caller skips it,
rather than pretending the lane is healthy.
"""
from __future__ import annotations

import time
from typing import Any

import requests

from app.core.config import settings

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API = "https://oauth.reddit.com"

# Reddit asks for a descriptive, contactable agent and rate-limits generic ones.
USER_AGENT = "python:my.arifaqyl.trafficmy:v1.0 (by /u/arifaqyl)"

_token: dict[str, Any] = {"value": None, "expires_at": 0.0}


def configured() -> bool:
    return bool(
        getattr(settings, "reddit_client_id", "")
        and getattr(settings, "reddit_client_secret", "")
    )


def _access_token() -> str | None:
    """Cached bearer token. Reddit issues these for ~24h; refresh a little early."""
    if not configured():
        return None
    now = time.time()
    if _token["value"] and now < _token["expires_at"]:
        return _token["value"]
    try:
        resp = requests.post(
            TOKEN_URL,
            auth=(settings.reddit_client_id, settings.reddit_client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError):
        return None

    token = payload.get("access_token")
    if not token:
        return None
    _token["value"] = token
    _token["expires_at"] = now + max(60, int(payload.get("expires_in", 3600)) - 120)
    return token


def _get(path: str, params: dict | None = None) -> dict | None:
    token = _access_token()
    if not token:
        return None
    try:
        resp = requests.get(
            f"{API}{path}",
            params=params or {},
            headers={"Authorization": f"bearer {token}", "User-Agent": USER_AGENT},
            timeout=25,
        )
        if resp.status_code == 401:      # token rejected — drop it and let the next call refresh
            _token["value"] = None
            return None
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, ValueError):
        return None


def _rows_from_listing(payload: dict | None, *, query: str) -> list[dict]:
    if not payload:
        return []
    out: list[dict] = []
    for child in payload.get("data", {}).get("children", []):
        d = child.get("data") or {}
        if d.get("stickied") or d.get("removed_by_category"):
            continue
        title = (d.get("title") or "").strip()
        body = (d.get("selftext") or "").strip()
        text = f"{title} {body}".strip()
        if not text:
            continue
        created = d.get("created_utc")
        if not created:
            continue
        out.append(
            {
                "source_platform": "reddit",
                "post_id": d.get("id") or d.get("name") or "",
                "url": "https://www.reddit.com" + (d.get("permalink") or ""),
                # Reddit exposes the author, but nothing downstream republishes it
                # and public_evidence() strips it before anything is served.
                "author_handle": d.get("author") or "",
                "created_at": _iso(created),
                "raw_text": text[:2000],
                "query": query,
                "subreddit": d.get("subreddit") or "",
            }
        )
    return out


def _iso(created_utc: float) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(float(created_utc), tz=UTC).isoformat().replace("+00:00", "Z")


def search(subreddit: str, query: str, *, limit: int = 25) -> list[dict]:
    """Recency-ordered search within one subreddit.

    sort=new matters: Reddit's default relevance ranking is what made the old
    news lane return years-old posts into a board that claims to show today.
    """
    payload = _get(
        f"/r/{subreddit}/search",
        {"q": query, "restrict_sr": 1, "sort": "new", "t": "week", "limit": limit},
    )
    return _rows_from_listing(payload, query=f"r/{subreddit}:{query}")


def newest(subreddit: str, *, limit: int = 50) -> list[dict]:
    """Straight /new listing — no query, pure recency."""
    payload = _get(f"/r/{subreddit}/new", {"limit": limit})
    return _rows_from_listing(payload, query=f"r/{subreddit}:new")


def health() -> dict:
    """Cheap probe used by diagnostics so a broken lane is visible, not silent."""
    if not configured():
        return {"ok": False, "reason": "unconfigured"}
    if not _access_token():
        return {"ok": False, "reason": "token_failed"}
    payload = _get("/r/malaysia/new", {"limit": 1})
    if payload is None:
        return {"ok": False, "reason": "request_failed"}
    n = len(payload.get("data", {}).get("children", []))
    return {"ok": n > 0, "reason": "ok" if n else "empty"}
