from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0 AduanMY research bot"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def fetch_html(url: str, *, headers: dict[str, str] | None = None, timeout: int = 20) -> str:
    response = requests.get(url, headers=headers or DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
    response.raise_for_status()
    return response.text


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

