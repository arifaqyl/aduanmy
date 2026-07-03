from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

from app.collectors.common import clean_text, fetch_html, make_post_id
from app.collectors.discovery import rss_feeds
from app.core.freshness import LIVE_WINDOW_DAYS, RECENT_DAYS
from app.pipeline.extract import category_signal_ok, extract_entity

STRIP_TAGS = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return clean_text(STRIP_TAGS.sub(" ", text or ""))


def _parse_pub_date(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _is_recent_enough(created_at: str, *, max_age_days: int = RECENT_DAYS) -> bool:
    if not created_at:
        return False
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed >= datetime.now(UTC) - timedelta(days=max_age_days)


def _row_ok(text: str, category: str) -> bool:
    entity = extract_entity(text, category)
    return category_signal_ok(text, category, entity)


def _parse_rss_items(xml_text: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    rows: list[dict[str, str]] = []
    for item in root.iter("item"):
        title = clean_text(item.findtext("title", ""))
        link = clean_text(item.findtext("link", ""))
        pub = _parse_pub_date(item.findtext("pubDate", ""))
        desc = _strip_html(item.findtext("description", ""))
        combined = clean_text(f"{title} {desc}")
        if not combined:
            continue
        rows.append(
            {
                "title": title,
                "url": link,
                "created_at": pub,
                "raw_text": combined,
            }
        )
    return rows


def collect_rss_sample() -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for feed in rss_feeds():
        try:
            xml_text = fetch_html(feed["url"], timeout=25)
        except Exception:
            continue
        for item in _parse_rss_items(xml_text)[:10]:
            text = item["raw_text"]
            category = feed["category"]
            if not _row_ok(text, category):
                continue
            created_at = item.get("created_at", "")
            if not _is_recent_enough(created_at):
                continue
            seed = item.get("url") or text[:120]
            post_id = make_post_id(seed)
            if post_id in seen:
                continue
            seen.add(post_id)
            out.append(
                {
                    "source_platform": "rss",
                    "post_id": post_id,
                    "url": item.get("url", ""),
                    "author_handle": feed.get("author_handle", "google-news"),
                    "created_at": created_at,
                    "raw_text": text,
                    "query": feed["url"],
                    "seed_category": category,
                }
            )
    return out
