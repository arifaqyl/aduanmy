from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
import re
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from app.collectors.common import clean_text, fetch_html, make_post_id, soup_from_html
from app.core.freshness import LIVE_WINDOW_DAYS

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional runtime dependency
    sync_playwright = None


OFFICIAL_SOURCES = [
    {
        "source_platform": "official",
        "url": "https://www.met.gov.my/en/info/data-terbuka/",
        "category": "flood_weather",
        "selectors": ["h1", "p"],
        "keywords": ["open data", "met api", "weather", "flood", "warning"],
    },
    {
        "source_platform": "official",
        "url": "https://data.gov.my/",
        "category": "gov_portals",
        "selectors": ["h1", "p"],
        "keywords": ["open data", "government", "dataset", "api"],
    },
    {
        "source_platform": "official",
        "url": "https://www.mot.gov.my/en/media/publication/open-data",
        "category": "transport",
        "selectors": ["h1", "p", "li"],
        "keywords": ["open data", "transport", "rail", "bus"],
    },
    {
        "source_platform": "official",
        "url": "https://easyfix.unifi.com.my/service-outage/",
        "category": "telco_internet",
        "selectors": ["h1", "h2", "h3", "p", "li"],
        "keywords": ["service outage", "interruption", "planned maintenance", "faulty network", "cable cuts"],
    },
]

MYRAPID_HOME = "https://myrapid.com.my/"
MYRAPID_ALERT_KEYWORDS = ("kemas kini", "kelewatan", "gangguan", "line update", "service alert")
MYRAPID_SEARCH_QUERIES = [
    'site:myrapid.com.my "kemas kini laluan" myrapid',
    'site:myrapid.com.my "kelewatan tren" myrapid',
    'site:myrapid.com.my "line update" "rapid kl"',
]
MYRAPID_NORMAL_STATUS_TERMS = (
    "normal service",
    "normal",
)
MYRAPID_RECENT_WINDOW_DAYS = LIVE_WINDOW_DAYS


def _looks_like_myrapid_alert_link(text: str, href: str) -> bool:
    low_text = clean_text(text).lower()
    low_href = href.lower()
    if not href.startswith("https://myrapid.com.my/"):
        return False
    if any(blocked in low_href for blocked in ["/pulse/mobile-app/", "/myrapid-performance/"]):
        return False
    return any(keyword in low_text for keyword in MYRAPID_ALERT_KEYWORDS)


def _myrapid_category(title: str, body: str) -> str:
    low = f"{title} {body}".lower()
    if any(token in low for token in ["bas", "laluan 3", "laluan 4", "trafik", "bus"]):
        return "transport"
    if any(token in low for token in ["line update", "laluan", "stesen", "tren", "lrt", "mrt", "monorel", "ampang", "kajang", "kelana jaya"]):
        return "transport"
    return "transport"


def _parse_myrapid_status_table_html(page_html: str) -> list[dict]:
    soup = soup_from_html(page_html)
    rows: list[dict] = []
    for table in soup.select("table"):
        headers = [clean_text(cell.get_text(" ", strip=True)).lower() for cell in table.select("tr th")]
        if not headers:
            continue
        joined = " ".join(headers)
        if "service line" not in joined and "status" not in joined:
            continue
        for tr in table.select("tr"):
            cells = [clean_text(cell.get_text(" ", strip=True)) for cell in tr.select("td")]
            if len(cells) < 2:
                continue
            line = cells[0]
            status = cells[1]
            remark = cells[2] if len(cells) >= 3 else ""
            if not line or not status:
                continue
            low_status = status.lower()
            if any(term in low_status for term in MYRAPID_NORMAL_STATUS_TERMS):
                continue
            raw_text = clean_text(f"{line} {status} {remark}")
            rows.append(
                {
                    "source_platform": "official",
                    "post_id": make_post_id(f"{MYRAPID_HOME}#{line}#{status}"),
                    "url": MYRAPID_HOME,
                    "author_handle": "official:myrapid:status-table",
                    "created_at": "",
                    "raw_text": raw_text,
                    "query": line,
                    "seed_category": "transport",
                }
            )
        if rows:
            break
    return rows


def _parse_myrapid_date(text: str) -> str:
    cleaned = clean_text(text).replace(".", " ")
    match = re.search(r"\b(\d{1,2}\s+[A-Za-z]+\s*,\s*\d{4})\b", cleaned)
    if match:
        cleaned = match.group(1)
    for fmt in ("%d %B, %Y", "%d %b, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def _is_recent_enough(created_at: str, *, max_age_days: int = MYRAPID_RECENT_WINDOW_DAYS) -> bool:
    if not created_at:
        return False
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed >= datetime.now(UTC) - timedelta(days=max_age_days)


def _bing_myrapid_results(search_html: str) -> list[dict]:
    soup = soup_from_html(search_html)
    results: list[dict] = []
    for item in soup.select("li.b_algo")[:6]:
        link = item.select_one("h2 a")
        snippet = item.select_one(".b_caption p")
        if not link:
            continue
        href = link.get("href", "")
        title = clean_text(link.get_text(" ", strip=True))
        body = clean_text(snippet.get_text(" ", strip=True) if snippet else "")
        if not href.startswith("https://myrapid.com.my/"):
            continue
        combined = clean_text(f"{title} {body}").lower()
        if not any(keyword in combined for keyword in MYRAPID_ALERT_KEYWORDS):
            continue
        results.append(
            {
                "href": href,
                "title": title,
                "body": body,
                "created_at": _parse_myrapid_date(f"{title} {body}"),
            }
        )
    return results


def _goto_with_retry(page, url: str, *, attempts: int = 2, wait_ms: int = 3000) -> bool:
    for _ in range(attempts):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(wait_ms)
            body_text = clean_text(page.locator("body").inner_text(timeout=4000))
            lowered = body_text.lower()
            if (
                body_text
                and "request unsuccessful" not in lowered
                and "additional security check is required" not in lowered
                and "i am human" not in lowered
            ):
                return True
        except Exception:
            continue
    return False


def _extract_page_focus(soup: BeautifulSoup, selectors: list[str], keywords: list[str]) -> str:
    seen: set[str] = set()
    parts: list[str] = []
    lowered_keywords = [keyword.lower() for keyword in keywords]

    def push(text: str) -> None:
        cleaned = clean_text(text)
        if len(cleaned) < 12:
            return
        lowered = cleaned.lower()
        if lowered in seen:
            return
        seen.add(lowered)
        parts.append(cleaned)

    for selector in selectors:
        for node in soup.select(selector):
            text = node.get_text(" ", strip=True)
            if not text:
                continue
            lowered = text.lower()
            if lowered_keywords and not any(keyword in lowered for keyword in lowered_keywords):
                continue
            push(text)
            if len(parts) >= 6:
                break
        if len(parts) >= 6:
            break

    if not parts:
        whole_text = clean_text(soup.get_text(" ", strip=True))
        for keyword in lowered_keywords:
            idx = whole_text.lower().find(keyword)
            if idx < 0:
                continue
            start = max(0, idx - 80)
            end = min(len(whole_text), idx + 220)
            push(whole_text[start:end])
            if len(parts) >= 4:
                break

    if not parts and soup.title:
        push(soup.title.get_text(" ", strip=True))

    return clean_text(" ".join(parts[:4]))


def _collect_myrapid_alerts(limit: int = 6) -> list[dict]:
    if sync_playwright is None:
        return []
    if os.getenv("PYTEST_CURRENT_TEST"):
        return []

    rows: list[dict] = []
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 2200},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        try:
            if not _goto_with_retry(page, MYRAPID_HOME):
                browser.close()
                return []
            page_html = page.content()
            status_rows = _parse_myrapid_status_table_html(page_html)
            for row in status_rows:
                rows.append(row)
                seen_urls.add(row["url"] + row["query"] + row["raw_text"])
                seen_titles.add(clean_text(row["raw_text"]).lower())
            links = page.locator("a").evaluate_all(
                """
                els => els.map(a => ({
                  text: (a.innerText || '').trim(),
                  href: a.href || ''
                }))
                """
            )
            alert_links = []
            for item in links:
                text = item.get("text", "")
                href = item.get("href", "")
                if not _looks_like_myrapid_alert_link(text, href):
                    continue
                title_key = clean_text(text).lower().split("|")[0].strip()
                if href in seen_urls:
                    continue
                if title_key in seen_titles:
                    continue
                seen_urls.add(href)
                seen_titles.add(title_key)
                alert_links.append({"text": text, "href": href})
                if len(alert_links) >= limit:
                    break

            for item in alert_links:
                title = clean_text(item["text"])
                if "service alerts" in title.lower():
                    continue
                rows.append(
                    {
                        "source_platform": "official",
                        "post_id": make_post_id(item["href"]),
                        "url": item["href"],
                        "author_handle": "official:myrapid",
                        "created_at": "",
                        "raw_text": title,
                        "query": title,
                        "seed_category": _myrapid_category(title, ""),
                    }
                )
        finally:
            browser.close()
    return rows


def _collect_myrapid_alerts_from_search(limit: int = 4) -> list[dict]:
    rows: list[dict] = []
    seen_urls: set[str] = set()
    for query in MYRAPID_SEARCH_QUERIES:
        search_url = f"https://www.bing.com/search?q={quote_plus(query)}"
        try:
            search_html = fetch_html(search_url, timeout=10)
        except Exception:
            continue
        for item in _bing_myrapid_results(search_html):
            href = item["href"]
            if href in seen_urls:
                continue
            if not _is_recent_enough(item["created_at"]):
                continue
            seen_urls.add(href)
            text = clean_text(f"{item['title']} {item['body']}")
            rows.append(
                {
                    "source_platform": "official",
                    "post_id": make_post_id(href),
                    "url": href,
                    "author_handle": "official:myrapid",
                    "created_at": item["created_at"],
                    "raw_text": text,
                    "query": item["title"],
                    "seed_category": _myrapid_category(item["title"], item["body"]),
                }
            )
            if len(rows) >= limit:
                return rows
    return rows


def collect_official_sample() -> list[dict]:
    rows: list[dict] = []
    rows.extend(_collect_myrapid_alerts())
    if not rows:
        rows.extend(_collect_myrapid_alerts_from_search())
    for source in OFFICIAL_SOURCES:
        source_platform = source["source_platform"]
        url = source["url"]
        seed_category = source["category"]
        try:
            html = fetch_html(url)
        except Exception:
            continue
        soup = soup_from_html(html)
        title = clean_text(soup.title.get_text(" ", strip=True) if soup.title else url)
        body = _extract_page_focus(
            soup,
            selectors=source.get("selectors", ["p"]),
            keywords=source.get("keywords", []),
        )
        rows.append(
            {
                "source_platform": source_platform,
                "post_id": make_post_id(url),
                "url": url,
                "author_handle": "official",
                "created_at": "",
                "raw_text": clean_text(f"{title} {body}"),
                "query": title,
                "seed_category": seed_category,
            }
        )
    return rows
