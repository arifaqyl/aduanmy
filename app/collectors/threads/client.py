from __future__ import annotations

import html
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus

from app.collectors.common import clean_text, fetch_html, make_post_id, soup_from_html
from app.core.freshness import LIVE_WINDOW_DAYS
from app.core.files import load_yaml
from app.pipeline.extract import classify_category, extract_entity, is_complaint_signal, transport_incident_signal_ok

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional dependency at runtime
    sync_playwright = None


RECENT_WINDOW_DAYS = LIVE_WINDOW_DAYS


def _bing_result_urls(search_html: str) -> list[tuple[str, str]]:
    soup = soup_from_html(search_html)
    results: list[tuple[str, str]] = []
    for item in soup.select("li.b_algo")[:5]:
        link = item.select_one("h2 a")
        snippet = item.select_one(".b_caption p")
        if not link:
            continue
        href = link.get("href", "")
        if "threads.com" not in href:
            continue
        results.append((href, clean_text(snippet.get_text(" ", strip=True) if snippet else "")))
    return results


def _extract_threads_text(page_html: str) -> str:
    meta = re.search(r'<meta property="og:description" content="([^"]+)"', page_html)
    if meta:
        return clean_text(html.unescape(meta.group(1)))
    return ""


def _looks_like_pinned_preview(text: str) -> bool:
    return clean_text(text).lower().startswith("pinned ")


def _is_profile_discovery_candidate(preview_text: str, exact_text: str, seed_category: str) -> bool:
    preview_text = clean_text(preview_text)
    exact_text = clean_text(exact_text)
    combined = clean_text(f"{preview_text} {exact_text}")
    if not combined:
        return False
    if seed_category == "transport":
        return transport_incident_signal_ok(combined)
    return is_complaint_signal(combined) or bool(classify_category(combined))


def _profile_url_from_post_url(url: str) -> str:
    match = re.search(r"(https://www\.threads\.com/@[^/]+)", url)
    return match.group(1) if match else url


def _playwright_post_timestamps(urls: list[str]) -> dict[str, str]:
    if sync_playwright is None or not urls:
        return {}
    timestamps: dict[str, str] = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 2200})
        for url in urls:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(1800)
                if page.locator("time").count():
                    created_at = page.locator("time").first.get_attribute("datetime") or ""
                    if created_at:
                        timestamps[url] = created_at
            except Exception:
                continue
        browser.close()
    return timestamps


def _playwright_profile_post_previews(profile_url: str, limit: int = 12) -> list[dict[str, str]]:
    if sync_playwright is None:
        return []
    rows: list[dict[str, str]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 2200})
        page.goto(profile_url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1800)
        for _ in range(2):
            batch = page.locator("a[href*='/post/']").evaluate_all(
                """
                els => els.map(a => {
                  let node = a;
                  let bestText = '';
                  let bestLen = 0;
                  for (let i = 0; i < 10 && node; i++, node = node.parentElement) {
                    const text = (node.innerText || '').trim();
                    const len = text.length;
                    if (len >= 40 && len <= 220 && len > bestLen) {
                      bestText = text;
                      bestLen = len;
                    }
                  }
                  const timeEl = a.querySelector('time') || a.closest('div')?.querySelector('time');
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
                if "/post/" not in href or href.endswith("/media"):
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
    deduped: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in rows:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        deduped.append(item)
    return deduped[:limit]


def _fill_missing_created_at(rows: list[dict]) -> list[dict]:
    missing_urls = [row["url"] for row in rows if row.get("url") and not row.get("created_at")]
    if not missing_urls:
        return rows
    timestamps = _playwright_post_timestamps(missing_urls)
    for row in rows:
        if not row.get("created_at"):
            row["created_at"] = timestamps.get(row["url"], "")
    return rows


def _is_recent_enough(created_at: str, *, max_age_days: int = RECENT_WINDOW_DAYS) -> bool:
    if not created_at:
        return False
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed >= datetime.now(UTC) - timedelta(days=max_age_days)


def collect_threads_sample() -> list[dict]:
    rows: list[dict] = []
    seed_urls = load_yaml("seed_urls.yaml").get("threads", [])
    seen_urls: set[str] = set()
    seed_rows: list[dict] = []
    for item in seed_urls:
        href = item["url"]
        seen_urls.add(href)
        try:
            page_html = fetch_html(href)
        except Exception:
            continue
        text = _extract_threads_text(page_html)
        if not text:
            continue
        seed_rows.append(
            {
                "source_platform": "threads",
                "post_id": make_post_id(href),
                "url": href,
                "author_handle": href.split("/@")[-1].split("/")[0] if "/@" in href else "threads",
                "created_at": "",
                "raw_text": text,
                "query": "seed_url",
                "seed_category": item["category"],
            }
        )
    _fill_missing_created_at(seed_rows)
    rows.extend(seed_rows)
    profile_map = {
        _profile_url_from_post_url(item["url"]): item["category"]
        for item in seed_urls
        if item.get("discover_profile")
    }
    for profile_url in profile_map:
        try:
            discovered_posts = _playwright_profile_post_previews(profile_url)
        except Exception:
            discovered_posts = []
        for item in discovered_posts:
            href = item["url"]
            if href in seen_urls:
                continue
            preview_text = clean_text(item.get("preview_text", ""))
            text = preview_text if preview_text and len(preview_text) >= 80 else ""
            if not text:
                try:
                    page_html = fetch_html(href, timeout=10)
                except Exception:
                    continue
                text = _extract_threads_text(page_html)
            if not _is_profile_discovery_candidate(preview_text, text, profile_map[profile_url]):
                continue
            seen_urls.add(href)
            rows.append(
                {
                    "source_platform": "threads",
                    "post_id": make_post_id(href),
                    "url": href,
                    "author_handle": href.split("/@")[-1].split("/")[0] if "/@" in href else "threads",
                    "created_at": item.get("created_at", ""),
                    "raw_text": text,
                    "query": "profile_discovery",
                    "seed_category": "",
                }
            )
    query_groups = load_yaml("queries.yaml").get("query_groups", {})
    for category, queries in query_groups.items():
        for query in queries[:2]:
            search_url = f"https://www.bing.com/search?q={quote_plus('site:threads.com ' + query + ' malaysia')}"
            try:
                search_html = fetch_html(search_url, timeout=10)
            except Exception:
                continue
            for href, snippet in _bing_result_urls(search_html):
                if snippet and not is_complaint_signal(snippet) and not classify_category(snippet):
                    continue
                try:
                    page_html = fetch_html(href, timeout=10)
                except Exception:
                    page_html = ""
                text = _extract_threads_text(page_html) or snippet
                if not text:
                    continue
                if href in seen_urls:
                    continue
                seen_urls.add(href)
                rows.append(
                    {
                        "source_platform": "threads",
                        "post_id": make_post_id(href),
                        "url": href,
                        "author_handle": href.split("/@")[-1].split("/")[0] if "/@" in href else "threads",
                        "created_at": "",
                        "raw_text": text,
                        "query": query,
                        "seed_category": category,
                    }
                )
    rows = _fill_missing_created_at(rows)
    return [row for row in rows if _is_recent_enough(row.get("created_at", ""))]
