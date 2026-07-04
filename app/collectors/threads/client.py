from __future__ import annotations

import html
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus, unquote

from app.collectors.common import clean_text, fetch_html, make_post_id, soup_from_html
from app.collectors.date_hints import created_at_from_text
from app.collectors.threads.session import load_storage_state, save_storage_state
from app.core.freshness import RECENT_DAYS, is_inside_myt_today
from app.collectors.discovery import threads_queries, threads_watchlist
from app.core.files import load_yaml
from app.pipeline.extract import (
    classify_category,
    is_complaint_signal,
    transport_incident_signal_ok,
    transport_rider_signal_worthwhile,
)

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional dependency at runtime
    sync_playwright = None


RECENT_WINDOW_DAYS = 1  # Today MYT only — rider reports must be same-day.
PROFILE_POST_LIMIT = 20
SEARCH_RESULT_LIMIT = 10
SEARCH_ROWS_PER_CATEGORY = 24
SEARCH_ROWS_PER_QUERY = 2
SEARCH_SCROLL_ROUNDS = 2
SEARCH_MAX_QUERIES_PER_CATEGORY = 12
SEARCH_CATEGORIES = ["transport"]
MANDATORY_TRANSPORT_QUERIES = (
    "rapidkl delay",
    "lrt kelana jaya line delay",
    "lrt ampang line delay",
    "lrt sri petaling line delay",
    "mrt kajang line delay",
    "mrt putrajaya line delay",
    "kl monorail delay",
    "lrt3 shah alam line",
    "ktm komuter delay",
)
SEARCH_POST_SELECTOR = "a[href*='/post/'], a[href*='/video/']"
_PLAYWRIGHT_LOCK = threading.Lock()

# Threads is the primary signal lane but the slowest — a stuck run must never eat the
# whole 15-min ingest cadence. Once the budget is spent we stop opening new pages and
# return whatever rows were already collected instead of blocking the scheduler.
THREADS_TIME_BUDGET_SECONDS = 150

_diagnostics_lock = threading.Lock()
_last_diagnostics: dict = {}


def _reset_diagnostics() -> None:
    with _diagnostics_lock:
        _last_diagnostics.clear()
        _last_diagnostics["reasons"] = []


def _note(key: str, value) -> None:
    with _diagnostics_lock:
        _last_diagnostics[key] = value


def _note_reason(reason: str) -> None:
    with _diagnostics_lock:
        _last_diagnostics.setdefault("reasons", []).append(reason)


def get_threads_diagnostics() -> dict:
    """Snapshot of why the most recent collect_threads_sample() run behaved as it did."""
    with _diagnostics_lock:
        return dict(_last_diagnostics)


def _budget_expired(deadline: float) -> bool:
    return time.monotonic() > deadline
SEARCH_POST_JS = """
els => els.map(a => {
  const href = a.href || '';
  if (!href || href.endsWith('/media')) return null;
  let node = a;
  let bestText = '';
  let bestLen = 0;
  for (let i = 0; i < 12 && node; i++, node = node.parentElement) {
    const text = (node.innerText || '').trim();
    const len = text.length;
    if (len >= 40 && len <= 400 && len > bestLen) {
      bestText = text;
      bestLen = len;
    }
  }
  const timeEl = a.querySelector('time') || a.closest('div')?.querySelector('time');
  return {
    href,
    preview_text: bestText,
    link_text: (a.innerText || '').trim(),
    created_at: timeEl ? (timeEl.getAttribute('datetime') || '') : ''
  };
}).filter(Boolean)
"""


def _new_threads_context(browser):
    options = {"viewport": {"width": 1280, "height": 2200}}
    state = load_storage_state()
    if state:
        options["storage_state"] = state
    return browser.new_context(**options), state is not None


def _page_has_authenticated_session(page) -> bool:
    """Confirm that Threads accepted the stored session after navigation."""
    try:
        return (
            page.locator("a[href='/activity']").count() > 0
            and page.locator("a[href*='/login']").count() == 0
            and page.get_by_text("Log in", exact=True).count() == 0
        )
    except Exception:
        return False


def _bing_result_urls(search_html: str) -> list[tuple[str, str]]:
    soup = soup_from_html(search_html)
    results: list[tuple[str, str]] = []
    for item in soup.select("li.b_algo")[:8]:
        link = item.select_one("h2 a")
        snippet = item.select_one(".b_caption p")
        if not link:
            continue
        href = link.get("href", "")
        if "threads.com" not in href:
            continue
        results.append((href, clean_text(snippet.get_text(" ", strip=True) if snippet else "")))
    return results


def _extract_threads_urls_from_html(page_html: str) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    seen: set[str] = set()
    for match in re.finditer(r"https?://(?:www\.)?threads\.com/@[^\"'\s<>]+", page_html):
        href = unquote(match.group(0).rstrip(".,;)"))
        if href in seen:
            continue
        if "/post/" not in href and "/video/" not in href:
            continue
        seen.add(href)
        urls.append((href, ""))
    return urls


def _duckduckgo_threads_results(query: str) -> list[tuple[str, str]]:
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus('site:threads.com ' + query + ' malaysia')}"
    try:
        search_html = fetch_html(search_url, timeout=15)
    except Exception:
        return []
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for encoded in re.findall(r'uddg=([^&"]+)', search_html):
        href = unquote(encoded)
        if "threads.com" not in href or href in seen:
            continue
        if "/post/" not in href and "/video/" not in href:
            continue
        seen.add(href)
        results.append((href, ""))
    results.extend(_extract_threads_urls_from_html(search_html))
    deduped: list[tuple[str, str]] = []
    seen.clear()
    for href, snippet in results:
        if href in seen:
            continue
        seen.add(href)
        deduped.append((href, snippet))
    return deduped[:8]


def _google_news_threads_results(query: str) -> list[tuple[str, str]]:
    rss_url = (
        f"https://news.google.com/rss/search?q={quote_plus('site:threads.com ' + query + ' malaysia')}"
        "&hl=en-MY&gl=MY&ceid=MY:en"
    )
    try:
        xml_text = fetch_html(rss_url, timeout=20)
        root = ET.fromstring(xml_text)
    except Exception:
        return []
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in root.iter("item"):
        combined = clean_text(
            f"{item.findtext('title', '')} {item.findtext('description', '')} {item.findtext('link', '')}"
        )
        for href, _ in _extract_threads_urls_from_html(combined):
            if href in seen:
                continue
            seen.add(href)
            results.append((href, combined[:220]))
        if len(results) >= 8:
            break
    return results


def _extract_threads_text(page_html: str) -> str:
    meta = re.search(r'<meta property="og:description" content="([^"]+)"', page_html)
    if meta:
        return clean_text(html.unescape(meta.group(1)))
    return ""


def _handle_from_threads_url(url: str) -> str:
    if "/@" not in url:
        return "threads"
    return url.split("/@")[-1].split("/")[0]


def _profile_url(handle: str) -> str:
    return f"https://www.threads.com/@{handle.lstrip('@')}"


def _looks_like_pinned_preview(text: str) -> bool:
    return clean_text(text).lower().startswith("pinned ")


def _looks_like_threads_signup_bait(text: str) -> bool:
    low = clean_text(text).lower()
    blocked = [
        "join threads to share ideas",
        "join threads to see what people are saying",
        "log in or sign up to view",
    ]
    return any(term in low for term in blocked)


def _looks_like_aggregated_feed_preview(text: str) -> bool:
    """Profile cards sometimes merge multiple posts into one preview blob."""
    return len(re.findall(r"\b\d+[hdw]\b", clean_text(text).lower())) >= 2


def _looks_like_reply_thread_blob(text: str) -> bool:
    low = clean_text(text).lower()
    if "replying to" in low and len(low) > 100:
        return True
    if re.search(r"replying to @\w+", low):
        return True
    return False


def _looks_like_foreign_platform_outage(text: str, category: str) -> bool:
    if category != "telco_internet":
        return False
    low = text.lower()
    foreign = ["facebook down", "instagram down", "whatsapp down", "meta down", "tiktok down"]
    malaysian = ["unifi", "maxis", "celcom", "digi", "time fibre", "telekom", "yes "]
    return any(term in low for term in foreign) and not any(term in low for term in malaysian)


def _is_usable_threads_row(row: dict) -> bool:
    text = clean_text(row.get("raw_text", ""))
    if not text or _looks_like_threads_signup_bait(text) or _looks_like_aggregated_feed_preview(text):
        return False
    if _looks_like_reply_thread_blob(text):
        return False
    category = row.get("seed_category", "")
    if _looks_like_foreign_platform_outage(text, category):
        return False
    return True


def _is_watchlist_candidate(preview_text: str, exact_text: str, category: str, role: str) -> bool:
    preview_text = clean_text(preview_text)
    exact_text = clean_text(exact_text)
    combined = clean_text(f"{preview_text} {exact_text}")
    if not combined:
        return False
    if category == "transport":
        return transport_rider_signal_worthwhile(combined)
    if category == "telco_internet":
        return (is_complaint_signal(combined) or classify_category(combined) == "telco_internet") and any(
            token in combined.lower()
            for token in ["unifi", "maxis", "celcom", "digi", "internet", "wifi", "broadband", "outage", "gangguan", "lambat"]
        )
    if category == "flood_weather":
        return classify_category(combined) == "flood_weather" or is_complaint_signal(combined)
    return is_complaint_signal(combined) or bool(classify_category(combined))


def _is_profile_discovery_candidate(preview_text: str, exact_text: str, seed_category: str) -> bool:
    return _is_watchlist_candidate(preview_text, exact_text, seed_category, "commuter")


def _profile_url_from_post_url(url: str) -> str:
    match = re.search(r"(https://www\.threads\.com/@[^/]+)", url)
    return match.group(1) if match else url


def _parse_created_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _sort_rows_by_created_at(rows: list[dict]) -> list[dict]:
    def sort_key(row: dict) -> datetime:
        parsed = _parse_created_at(row.get("created_at", ""))
        return parsed or datetime.min.replace(tzinfo=UTC)

    return sorted(rows, key=sort_key, reverse=True)


def _transport_queries_for_run() -> list[str]:
    """Search every major Klang Valley rail line; rotate wider national terms."""
    available = list(dict.fromkeys(threads_queries("transport")))
    core = list(MANDATORY_TRANSPORT_QUERIES)
    rotating = [query for query in available if query not in core]
    if not rotating:
        return core
    slot = int(datetime.now(UTC).timestamp() // (15 * 60))
    start = (slot * 2) % len(rotating)
    window = [rotating[(start + offset) % len(rotating)] for offset in range(3)]
    return core + window


# Threads' DOM often glues "<handle> <relative_time>" onto the caption with
# no separator — e.g. "pixel.stuck 9m Another hard race on...". Left in place,
# a username fragment like ".stuck" or ".delayed" reads as post content and
# has previously caused unrelated posts (foreign motocross races, etc.) to be
# misread as live rider signals. Strip it before any keyword classification.
_LEADING_HANDLE_TIME = re.compile(r"^@?[a-z0-9_.]{2,40}\s+\d{1,3}\s*[smhdw]\b\s*", re.IGNORECASE)


def _strip_leading_handle_time(text: str) -> str:
    stripped = _LEADING_HANDLE_TIME.sub("", text, count=1).strip()
    return stripped or text


def _clean_search_preview(preview_text: str) -> str:
    """Pick the most content-like line from a Threads search card blob."""
    lines = [clean_text(line) for line in preview_text.splitlines() if clean_text(line)]
    if not lines:
        return ""
    blocked = re.compile(r"^(\d+[hdwms]?|\d{1,2}/\d{1,2}/\d{2,4}|@\w+|facebook|instagram)$", re.I)
    candidates = [line for line in lines if not blocked.match(line) and len(line) >= 12]
    if not candidates:
        candidates = lines
    best = max(candidates, key=len)
    return _strip_leading_handle_time(best)


def _is_search_result_candidate(text: str, category: str) -> bool:
    text = clean_text(text)
    if not text or _looks_like_reply_thread_blob(text) or _looks_like_foreign_platform_outage(text, category):
        return False
    if category == "transport":
        return transport_rider_signal_worthwhile(text)
    if category == "telco_internet":
        return classify_category(text) == "telco_internet" or (
            is_complaint_signal(text)
            and any(token in text.lower() for token in ["unifi", "maxis", "celcom", "digi", "internet", "wifi", "broadband"])
        )
    if category == "flood_weather":
        return classify_category(text) == "flood_weather" or is_complaint_signal(text)
    return is_complaint_signal(text) or bool(classify_category(text))


def _scrape_threads_search_page(page, query: str, limit: int = SEARCH_RESULT_LIMIT) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    search_url = f"https://www.threads.com/search?q={quote_plus(query)}&filter=recent"
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=35000)
        page.wait_for_timeout(1500)
        for _ in range(SEARCH_SCROLL_ROUNDS):
            batch = page.locator(SEARCH_POST_SELECTOR).evaluate_all(SEARCH_POST_JS)
            for item in batch:
                href = item.get("href", "")
                preview_text = clean_text(item.get("preview_text", ""))
                link_text = clean_text(item.get("link_text", ""))
                created_at = item.get("created_at", "") or created_at_from_text(preview_text) or created_at_from_text(link_text)
                rows.append(
                    {
                        "url": href,
                        "preview_text": preview_text,
                        "link_text": link_text,
                        "created_at": created_at,
                    }
                )
            if len({item["url"] for item in rows}) >= limit:
                break
            page.mouse.wheel(0, 2400)
            page.wait_for_timeout(500)
    except Exception:
        return []

    deduped: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for item in rows:
        if item["url"] in seen_urls:
            continue
        seen_urls.add(item["url"])
        deduped.append(item)
    return _sort_rows_by_created_at(deduped)[:limit]


def _playwright_threads_search_results(query: str, limit: int = SEARCH_RESULT_LIMIT) -> list[dict[str, str]]:
    """Scrape threads.com/search for the latest posts matching a keyword."""
    if sync_playwright is None or not clean_text(query):
        return []
    try:
        with _PLAYWRIGHT_LOCK:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context, _authenticated = _new_threads_context(browser)
                page = context.new_page()
                rows = _scrape_threads_search_page(page, query, limit=limit)
                context.close()
                browser.close()
                return rows
    except Exception:
        return []


def _playwright_post_timestamps(urls: list[str]) -> dict[str, str]:
    if sync_playwright is None or not urls:
        return {}
    timestamps: dict[str, str] = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context, _authenticated = _new_threads_context(browser)
            page = context.new_page()
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
            context.close()
            browser.close()
    except Exception:
        return timestamps
    return timestamps


def _playwright_profile_post_previews(profile_url: str, limit: int = PROFILE_POST_LIMIT) -> list[dict[str, str]]:
    if sync_playwright is None:
        return []
    rows: list[dict[str, str]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context, _authenticated = _new_threads_context(browser)
            page = context.new_page()
            page.goto(profile_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2000)
            for _ in range(4):
                batch = page.locator("a[href*='/post/'], a[href*='/video/']").evaluate_all(
                    """
                    els => els.map(a => {
                      const href = a.href || '';
                      if (!href || href.endsWith('/media')) {
                        return null;
                      }
                      let node = a;
                      let bestText = '';
                      let bestLen = 0;
                      for (let i = 0; i < 12 && node; i++, node = node.parentElement) {
                        const text = (node.innerText || '').trim();
                        const len = text.length;
                        if (len >= 35 && len <= 320 && len > bestLen) {
                          bestText = text;
                          bestLen = len;
                        }
                      }
                      const timeEl = a.querySelector('time') || a.closest('div')?.querySelector('time');
                      return {
                        href,
                        preview_text: bestText,
                        created_at: timeEl ? (timeEl.getAttribute('datetime') || '') : ''
                      };
                    }).filter(Boolean)
                    """
                )
                for item in batch:
                    href = item.get("href", "")
                    preview_text = clean_text(item.get("preview_text", ""))
                    if _looks_like_pinned_preview(preview_text):
                        continue
                    created_at = item.get("created_at", "") or created_at_from_text(preview_text)
                    rows.append(
                        {
                            "url": href,
                            "preview_text": preview_text,
                            "created_at": created_at,
                        }
                    )
                if len({item["url"] for item in rows}) >= limit:
                    break
                page.mouse.wheel(0, 2800)
                page.wait_for_timeout(1000)
            context.close()
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
    deduped = _sort_rows_by_created_at(deduped)
    return deduped[:limit]


def _apply_text_created_at(row: dict) -> None:
    if row.get("created_at"):
        return
    created_at = created_at_from_text(row.get("raw_text", ""))
    if not created_at:
        created_at = created_at_from_text(row.get("preview_text", ""))
    if created_at:
        row["created_at"] = created_at


def _fill_missing_created_at(rows: list[dict]) -> list[dict]:
    for row in rows:
        _apply_text_created_at(row)
    missing_urls = [row["url"] for row in rows if row.get("url") and not row.get("created_at")]
    if missing_urls:
        timestamps = _playwright_post_timestamps(missing_urls[:5])
        for row in rows:
            if not row.get("created_at"):
                row["created_at"] = timestamps.get(row["url"], "")
    for row in rows:
        _apply_text_created_at(row)
    return rows


def _is_recent_enough(created_at: str, *, max_age_days: int = RECENT_WINDOW_DAYS) -> bool:
    if not created_at:
        return False
    parsed = _parse_created_at(created_at)
    if parsed is None:
        return False
    if max_age_days <= 1:
        return is_inside_myt_today(created_at)
    return parsed >= datetime.now(UTC) - timedelta(days=max_age_days)


def _make_threads_row(
    *,
    url: str,
    raw_text: str,
    query: str,
    seed_category: str,
    created_at: str = "",
    preview_text: str = "",
    collection_method: str = "",
) -> dict:
    row = {
        "source_platform": "threads",
        "post_id": make_post_id(url),
        "url": url,
        "author_handle": _handle_from_threads_url(url),
        "created_at": created_at,
        "raw_text": raw_text,
        "query": query,
        "seed_category": seed_category,
    }
    if preview_text:
        row["preview_text"] = preview_text
    if collection_method:
        row["collection_method"] = collection_method
    return row


def _resolve_threads_text(url: str, preview_text: str = "", snippet: str = "") -> str:
    text = _strip_leading_handle_time(clean_text(preview_text))
    if text and len(text) >= 20:
        return text
    try:
        page_html = fetch_html(url, timeout=10)
    except Exception:
        page_html = ""
    resolved = _extract_threads_text(page_html) or clean_text(snippet)
    return _strip_leading_handle_time(resolved)


def _collect_keyword_search_posts(seen_urls: set[str], *, deadline: float | None = None) -> list[dict]:
    """Primary lane: native Threads keyword search for latest complaint posts."""
    if sync_playwright is None:
        _note_reason("playwright_not_installed")
        return []
    rows: list[dict] = []
    queries_run = 0
    queries_with_hits = 0
    try:
        with _PLAYWRIGHT_LOCK:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context, session_loaded = _new_threads_context(browser)
                page = context.new_page()
                authenticated = False
                session_checked = False
                for category in SEARCH_CATEGORIES:
                    category_rows = 0
                    queries = _transport_queries_for_run()
                    for query_index, query in enumerate(queries):
                        if deadline is not None and _budget_expired(deadline):
                            _note_reason(f"keyword_search_time_budget_exceeded_after_{queries_run}_queries")
                            break
                        mandatory = query_index < len(MANDATORY_TRANSPORT_QUERIES)
                        if not mandatory and category_rows >= SEARCH_ROWS_PER_CATEGORY:
                            break
                        hits = _scrape_threads_search_page(page, query)
                        queries_run += 1
                        if hits:
                            queries_with_hits += 1
                        if not session_checked:
                            authenticated = session_loaded and _page_has_authenticated_session(page)
                            session_checked = True
                            _note("session_loaded", session_loaded)
                            _note("authenticated", authenticated)
                            if session_loaded and not authenticated:
                                _note_reason("session_expired_or_login_wall")
                        query_rows = 0
                        for item in hits:
                            if query_rows >= SEARCH_ROWS_PER_QUERY or category_rows >= SEARCH_ROWS_PER_CATEGORY:
                                break
                            href = item["url"]
                            if href in seen_urls:
                                continue
                            preview_text = clean_text(item.get("preview_text", ""))
                            link_text = clean_text(item.get("link_text", ""))
                            created_at = item.get("created_at", "") or created_at_from_text(preview_text) or created_at_from_text(link_text)
                            if created_at and not _is_recent_enough(created_at):
                                continue
                            snippet = _clean_search_preview(preview_text) or _strip_leading_handle_time(link_text)
                            text = snippet if len(snippet) >= 20 else _resolve_threads_text(href, preview_text=snippet)
                            if not text:
                                continue
                            if not _is_search_result_candidate(text, category):
                                continue
                            seen_urls.add(href)
                            rows.append(
                                _make_threads_row(
                                    url=href,
                                    raw_text=text,
                                    query=query,
                                    seed_category=category,
                                    created_at=created_at,
                                    preview_text=preview_text,
                                    collection_method=(
                                        "authenticated_web_search" if authenticated else "public_web_search"
                                    ),
                                )
                            )
                            category_rows += 1
                            query_rows += 1
                if authenticated:
                    save_storage_state(context.storage_state())
                context.close()
                browser.close()
    except Exception as exc:
        _note_reason(f"keyword_search_exception:{type(exc).__name__}")
        return rows
    finally:
        _note("keyword_search_queries_run", queries_run)
        _note("keyword_search_queries_with_hits", queries_with_hits)
        _note("keyword_search_rows", len(rows))
        if queries_run and queries_with_hits == 0:
            _note_reason("search_blocked_or_no_results_all_queries")
    return rows


def _collect_latest_watchlist_posts(seen_urls: set[str]) -> list[dict]:
    rows: list[dict] = []
    for category in SEARCH_CATEGORIES:
        for item in threads_watchlist(category):
            handle = item.get("handle", "")
            role = item.get("role", "commuter")
            if not handle:
                continue
            profile_url = _profile_url(handle)
            try:
                discovered_posts = _playwright_profile_post_previews(profile_url)
            except Exception:
                discovered_posts = []
            for post in discovered_posts:
                href = post["url"]
                if href in seen_urls:
                    continue
                preview_text = clean_text(post.get("preview_text", ""))
                created_at = post.get("created_at", "") or created_at_from_text(preview_text)
                if created_at and not _is_recent_enough(created_at):
                    continue
                text = _resolve_threads_text(href, preview_text=preview_text)
                if not text:
                    continue
                if not _is_watchlist_candidate(preview_text, text, category, role):
                    continue
                seen_urls.add(href)
                rows.append(
                    _make_threads_row(
                        url=href,
                        raw_text=text,
                        query="latest_profile",
                        seed_category=category,
                        created_at=created_at,
                        preview_text=preview_text,
                    )
                )
    return rows


def _web_search_hits(query: str) -> list[tuple[str, str]]:
    """Run external search engines in parallel — does not block Playwright lane."""
    hits: list[tuple[str, str]] = []
    seen: set[str] = set()

    def bing() -> list[tuple[str, str]]:
        bing_url = f"https://www.bing.com/search?q={quote_plus('site:threads.com ' + query)}&filters=ex1:\"ez2\""
        try:
            return _bing_result_urls(fetch_html(bing_url, timeout=12))
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(bing): "bing",
            pool.submit(_duckduckgo_threads_results, query): "ddg",
            pool.submit(_google_news_threads_results, query): "news",
        }
        for future in as_completed(futures):
            try:
                batch = future.result()
            except Exception:
                continue
            for href, snippet in batch:
                if href in seen:
                    continue
                seen.add(href)
                hits.append((href, snippet))
    return hits


def _collect_search_discovered_posts(seen_urls: set[str]) -> list[dict]:
    """Fallback lane: external search engines when native search misses."""
    rows: list[dict] = []
    for category in SEARCH_CATEGORIES:
        for query in threads_queries(category)[:SEARCH_MAX_QUERIES_PER_CATEGORY]:
            for href, snippet in _web_search_hits(query):
                if href in seen_urls:
                    continue
                text = _resolve_threads_text(href, snippet=snippet)
                if not text:
                    continue
                if not _is_search_result_candidate(text, category):
                    continue
                seen_urls.add(href)
                rows.append(
                    _make_threads_row(
                        url=href,
                        raw_text=text,
                        query=f"web:{query}",
                        seed_category=category,
                    )
                )
    return rows


def _collect_seed_posts(seen_urls: set[str], *, skip_profile_discovery: bool = False) -> list[dict]:
    rows: list[dict] = []
    for item in load_yaml("seed_urls.yaml").get("threads", []):
        if item.get("category") != "transport":
            continue
        href = item["url"]
        if href in seen_urls:
            continue
        seen_urls.add(href)
        try:
            page_html = fetch_html(href)
        except Exception:
            continue
        text = _extract_threads_text(page_html)
        if not text:
            continue
        rows.append(
            _make_threads_row(
                url=href,
                raw_text=text,
                query="seed_url",
                seed_category=item["category"],
            )
        )

    if skip_profile_discovery:
        return rows

    profile_map = {
        _profile_url_from_post_url(item["url"]): item["category"]
        for item in load_yaml("seed_urls.yaml").get("threads", [])
        if item.get("category") == "transport" and item.get("discover_profile")
    }
    for profile_url, seed_category in profile_map.items():
        try:
            discovered_posts = _playwright_profile_post_previews(profile_url)
        except Exception:
            discovered_posts = []
        for post in discovered_posts:
            href = post["url"]
            if href in seen_urls:
                continue
            preview_text = clean_text(post.get("preview_text", ""))
            text = _resolve_threads_text(href, preview_text=preview_text)
            if not _is_profile_discovery_candidate(preview_text, text, seed_category):
                continue
            seen_urls.add(href)
            rows.append(
                _make_threads_row(
                    url=href,
                    raw_text=text,
                    query="profile_discovery",
                    seed_category=seed_category,
                    created_at=post.get("created_at", ""),
                    preview_text=preview_text,
                )
            )
    return rows


def collect_threads_sample() -> list[dict]:
    _reset_diagnostics()
    started = time.monotonic()
    deadline = started + THREADS_TIME_BUDGET_SECONDS
    seen_urls: set[str] = set()
    rows: list[dict] = []
    rows.extend(_collect_keyword_search_posts(seen_urls, deadline=deadline))
    if len(rows) < 6 and not _budget_expired(deadline):
        rows.extend(_collect_latest_watchlist_posts(seen_urls))
    elif _budget_expired(deadline):
        _note_reason("skipped_watchlist_lane_time_budget")
    if len(rows) < 6 and not _budget_expired(deadline):
        rows.extend(_collect_search_discovered_posts(seen_urls))
    elif _budget_expired(deadline):
        _note_reason("skipped_web_search_fallback_lane_time_budget")
    if not _budget_expired(deadline):
        rows.extend(_collect_seed_posts(seen_urls, skip_profile_discovery=len(rows) >= 10))
    else:
        _note_reason("skipped_seed_posts_lane_time_budget")

    _note("raw_rows_before_filter", len(rows))
    rows = _fill_missing_created_at(rows)
    rows = _sort_rows_by_created_at(rows)
    filtered = [
        row
        for row in rows
        if _is_usable_threads_row(row)
        and _is_recent_enough(row.get("created_at", ""), max_age_days=1)
        and (
            row.get("seed_category") != "transport"
            or transport_rider_signal_worthwhile(row.get("raw_text", ""))
        )
    ]
    _note("filtered_rows", len(filtered))
    _note("duration_seconds", round(time.monotonic() - started, 1))
    if rows and not filtered:
        _note_reason("all_candidate_rows_rejected_by_today_or_rider_signal_filters")
    if not rows:
        _note_reason("no_posts_discovered_today")
    return filtered
