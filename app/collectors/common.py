from __future__ import annotations

import hashlib
import json
import random
import re
import time
from datetime import UTC, datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

DEFAULT_HEADERS = {"User-Agent": USER_AGENTS[0]}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _is_transient(exc: Exception) -> bool:
    """True for errors worth retrying: connection/timeout, 429, or 5xx."""
    if isinstance(exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status is None:
            return True
        return status == 429 or status >= 500
    return False


def fetch_html(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 20,
    max_retries: int = 2,
) -> str:
    """Fetch a page with retry + User-Agent rotation for transient failures.

    Retries connection/timeout/429/5xx errors up to ``max_retries`` extra
    attempts with small exponential backoff. Permanent 4xx errors (except 429)
    raise immediately. An explicit ``User-Agent`` in ``headers`` is honored over
    rotation.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        merged = {"User-Agent": USER_AGENTS[attempt % len(USER_AGENTS)]}
        if headers:
            merged.update(headers)
        try:
            response = requests.get(url, headers=merged, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if attempt < max_retries and _is_transient(exc):
                time.sleep(0.4 * (2 ** attempt) + random.uniform(0, 0.2))
                continue
            raise
    assert last_exc is not None  # pragma: no cover - loop always returns or raises
    raise last_exc  # pragma: no cover



def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text


def make_post_id(seed: str) -> str:
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]


def dump_json(path: str, payload: Any) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)

