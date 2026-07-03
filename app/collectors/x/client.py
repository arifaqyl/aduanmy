from __future__ import annotations

import html
import json
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus

from app.collectors.common import clean_text, fetch_html, make_post_id, soup_from_html
from app.core.config import settings
from app.core.freshness import LIVE_WINDOW_DAYS
from app.collectors.discovery import x_queries
from app.core.files import load_yaml
from app.pipeline.extract import classify_category, is_complaint_signal

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional runtime dependency
    sync_playwright = None


RECENT_WINDOW_DAYS = LIVE_WINDOW_DAYS
TRUSTED_TRANSPORT_HANDLES = {"askrapidkl", "myrapidkl", "ktmb"}
X_DISCOVERY_QUERIES = {
    "transport": [
        "askrapidkl delay",
        "myrapidkl line update",
        "kelana jaya line delay",
        "ampang sri petaling line update",
    ],
    "telco_internet": [
        "unifi down",
        "maxis outage",
    ],
    "banking_payments": [
        "duitnow pending",
        "mae problem",
    ],
    "gov_portals": [
        "myjpj error",
        "kwsp app down",
    ],
    "flood_weather": [
        "banjir kl",
        "jalan tutup hujan lebat",
    ],
}


def _bing_x_results(search_html: str) -> list[tuple[str, str]]:
    soup = soup_from_html(search_html)
    results: list[tuple[str, str]] = []
    for item in soup.select("li.b_algo")[:5]:
        link = item.select_one("h2 a")
        snippet = item.select_one(".b_caption p")
        if not link:
            continue
        href = link.get("href", "")
        if "x.com" not in href or "/status/" not in href:
            continue
        results.append((href, clean_text(snippet.get_text(" ", strip=True) if snippet else "")))
    return results


def _extract_x_text(page_html: str) -> str:
    for pat in [
        r'<meta content="([^"]+)" property="og:description"',
        r'<meta property="og:description" content="([^"]+)"',
        r'<meta content="([^"]+)" property="og:title"',
        r"<title>(.*?)</title>",
    ]:
        match = re.search(pat, page_html, re.S)
        if match:
            return clean_text(html.unescape(match.group(1)))
    return ""


def _fxtwitter_status_text(url: str) -> str:
    match = re.search(r"x\.com/([^/]+)/status/(\d+)", url)
    if not match:
        return ""
    handle, status_id = match.group(1), match.group(2)
    api_url = f"https://api.fxtwitter.com/{handle}/status/{status_id}"
    try:
        payload = json.loads(fetch_html(api_url, timeout=15))
    except Exception:
        return ""
    tweet = payload.get("tweet") if isinstance(payload, dict) else None
    if not isinstance(tweet, dict):
        return ""
    return clean_text(tweet.get("text", ""))


def _fetch_x_status_text(url: str) -> str:
    try:
        page_html = fetch_html(url, timeout=10)
    except Exception:
        page_html = ""
    return _extract_x_text(page_html) or _fxtwitter_status_text(url)


def _looks_like_pinned_preview(text: str) -> bool:
    return clean_text(text).lower().startswith("pinned ")


def _is_trusted_transport_handle(handle: str) -> bool:
    return clean_text(handle).lower().lstrip("@") in TRUSTED_TRANSPORT_HANDLES


def _is_x_row_signal(text: str, *, handle: str = "") -> bool:
    if not clean_text(text):
        return False
    if _is_trusted_transport_handle(handle):
        low = text.lower()
        incident_terms = [
            "line update",
            "kelewatan",
            "delay",
            "gangguan",
            "incident",
            "experiencing",
            "kemas kini",
            "service alert",
            "manual",
            "terjejas",
            "bas perantara",
            "help and rescue",
        ]
        blocked = [
            "support channel is now focused",
            "reach us through other channels for support",
            "saluran sokongan x kami kini fokus",
        ]
        if any(term in low for term in blocked):
            return False
        return any(term in low for term in incident_terms)
    return is_complaint_signal(text) or _is_x_incident_signal(text)


def _x_created_at_from_status_url(url: str) -> str:
    match = re.search(r"/status/(\d+)", url)
    if not match:
        return ""
    try:
        status_id = int(match.group(1))
    except ValueError:
        return ""
    # X/Twitter snowflake epoch in milliseconds
    ts_ms = (status_id >> 22) + 1288834974657
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
    except (OverflowError, OSError, ValueError):
        return ""
    return dt.isoformat().replace("+00:00", "Z")


def _is_recent_enough(created_at: str, *, max_age_days: int = RECENT_WINDOW_DAYS) -> bool:
    if not created_at:
        return False
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed >= datetime.now(UTC) - timedelta(days=max_age_days)


def _profile_url_from_seed(url: str) -> str | None:
    if "x.com/" not in url:
        return None
    tail = url.split("x.com/")[-1].strip("/")
    if not tail or tail.startswith("search") or tail.startswith("hashtag") or "/status/" in tail:
        return None
    handle = tail.split("/")[0]
    if not handle or "?" in handle:
        return None
    return f"https://x.com/{handle}"


def _profile_handle(profile_url: str) -> str:
    return profile_url.rstrip("/").split("x.com/")[-1].split("/")[0]


def _is_x_incident_signal(text: str) -> bool:
    low = text.lower()
    terms = [
        "incident",
        "line update",
        "experiencing",
        "delay",
        "lambat",
        "gangguan",
        "kelewatan",
        "tak boleh",
        "not working",
        "problem",
        "issue",
        "pending",
        "fire alarm",
        "help and rescue",
        "apologies for the inconvenience",
    ]
    blocked = [
        "focused on service updates and announcements",
        "reach us through other channels for support",
        "support channel is now focused",
    ]
    if any(term in low for term in blocked):
        return False
    return any(term in low for term in terms)


def _syndication_profile_status_urls(profile_url: str, limit: int = 10) -> list[str]:
    handle = _profile_handle(profile_url)
    if not handle:
        return []
    syndication_url = f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{handle}"
    try:
        page_html = fetch_html(syndication_url, timeout=20)
    except Exception:
        return []
    status_ids = list(dict.fromkeys(re.findall(r"/status/(\d+)", page_html)))
    return [f"https://x.com/{handle}/status/{status_id}" for status_id in status_ids[:limit]]


def _playwright_profile_status_previews(profile_url: str, limit: int = 10) -> list[dict[str, str]]:
    if sync_playwright is None:
        return []
    rows: list[dict[str, str]] = []
    expected_handle = _profile_handle(profile_url)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 2200})
            page.goto(profile_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1800)
            for _ in range(2):
                batch = page.locator("a[href*='/status/']").evaluate_all(
                    """
                    els => els.map(a => {
                      let node = a;
                      let bestText = '';
                      let bestLen = 0;
                      for (let i = 0; i < 10 && node; i++, node = node.parentElement) {
                        const text = (node.innerText || '').trim();
                        const len = text.length;
                        if (len >= 50 && len <= 700 && len > bestLen) {
                          bestText = text;
                          bestLen = len;
                        }
                      }
                      const timeEl = a.querySelector('time') || a.closest('article')?.querySelector('time') || a.closest('div')?.querySelector('time');
                      return {
                        href: a.href,
                        preview_text: bestText,
                        created_at: timeEl ? (timeEl.getAttribute('datetime') || '') : ''
                      };
                    })
                    """
                )
                for item in batch:
                    href = item.get("href", "")
                    if "/status/" not in href or "/photo/" in href or "/quotes" in href:
                        continue
                    if f"x.com/{expected_handle}/status/" not in href:
                        continue
                    preview_text = clean_text(item.get("preview_text", ""))
                    if _looks_like_pinned_preview(preview_text):
                        continue
                    rows.append(
                        {
                            "url": href,
                            "preview_text": preview_text,
                            "created_at": item.get("created_at", ""),
                        }
                    )
                if len({item["url"] for item in rows}) >= limit:
                    break
                page.mouse.wheel(0, 2400)
                page.wait_for_timeout(900)
            browser.close()
    except Exception:
        return []

    deduped: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in rows:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        deduped.append(item)
    return deduped[:limit]


def collect_x_sample() -> list[dict]:
    rows: list[dict] = []
    seen_urls: set[str] = set()
    seed_urls = load_yaml("seed_urls.yaml").get("x", [])

    for item in seed_urls:
        href = item["url"]
        if "/status/" in href:
            created_at = _x_created_at_from_status_url(href)
            if not _is_recent_enough(created_at):
                continue
            try:
                page_html = fetch_html(href, timeout=10)
            except Exception:
                page_html = ""
            raw_text = _extract_x_text(page_html) or _fxtwitter_status_text(href) or clean_text(item.get("fallback_text", ""))
            if not raw_text:
                continue
            seen_urls.add(href)
            rows.append(
                {
                    "source_platform": "x",
                    "post_id": make_post_id(href),
                    "url": href,
                    "author_handle": href.split("x.com/")[-1].split("/")[0] if "x.com/" in href else "x",
                    "created_at": created_at,
                    "raw_text": raw_text,
                    "query": "seed_status",
                    "seed_category": item["category"],
                }
            )

    profile_map: dict[str, str] = {}
    for item in seed_urls:
        if not item.get("discover_profile"):
            continue
        profile_url = _profile_url_from_seed(item["url"])
        if profile_url:
            profile_map[profile_url] = item["category"]

    for profile_url, fallback_category in profile_map.items():
        discovered: list[dict[str, str]] = []
        syndication_urls = _syndication_profile_status_urls(profile_url)
        recent_syndication = [
            href
            for href in syndication_urls
            if _is_recent_enough(_x_created_at_from_status_url(href))
        ]
        if recent_syndication:
            discovered = [
                {
                    "url": href,
                    "preview_text": "",
                    "created_at": _x_created_at_from_status_url(href),
                }
                for href in recent_syndication
            ]
        elif settings.discovery_depth == "full":
            try:
                discovered = _playwright_profile_status_previews(profile_url)
            except Exception:
                discovered = []
        for item in discovered:
            href = item["url"]
            if href in seen_urls:
                continue
            created_at = item.get("created_at", "") or _x_created_at_from_status_url(href)
            if not _is_recent_enough(created_at):
                continue
            handle = href.split("x.com/")[-1].split("/")[0] if "x.com/" in href else ""
            preview_text = clean_text(item.get("preview_text", ""))
            if _looks_like_pinned_preview(preview_text):
                continue
            raw_text = preview_text if preview_text and len(preview_text) >= 90 else ""
            if not raw_text:
                raw_text = _fetch_x_status_text(href)
            if not _is_x_row_signal(preview_text or raw_text, handle=handle):
                continue
            if not raw_text:
                continue
            seen_urls.add(href)
            preview_category = classify_category(raw_text)
            rows.append(
                {
                    "source_platform": "x",
                    "post_id": make_post_id(href),
                    "url": href,
                    "author_handle": handle or "x",
                    "created_at": created_at,
                    "raw_text": raw_text,
                    "query": "profile_discovery",
                    "seed_category": fallback_category if not preview_category else "",
                }
            )

    if settings.discovery_depth == "full":
        categories = ["transport", "telco_internet", "flood_weather"]
        for category in categories:
            search_queries = x_queries(category) or X_DISCOVERY_QUERIES.get(category, [])
            for query in search_queries:
                search_url = f"https://www.bing.com/search?q={quote_plus('site:x.com/status ' + query + ' malaysia')}"
                try:
                    search_html = fetch_html(search_url, timeout=10)
                except Exception:
                    continue
                for href, snippet in _bing_x_results(search_html):
                    if href in seen_urls:
                        continue
                    created_at = _x_created_at_from_status_url(href)
                    if not _is_recent_enough(created_at):
                        continue
                    if not snippet:
                        continue
                    seen_urls.add(href)
                    rows.append(
                        {
                            "source_platform": "x",
                            "post_id": make_post_id(href),
                            "url": href,
                            "author_handle": href.split("x.com/")[-1].split("/")[0] if "x.com/" in href else "x",
                            "created_at": created_at,
                            "raw_text": snippet,
                            "query": query,
                            "seed_category": category,
                        }
                    )
    return rows
