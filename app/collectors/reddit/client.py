from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from urllib.parse import quote_plus

from app.collectors.common import clean_text, fetch_html, make_post_id, soup_from_html
from app.core.freshness import LIVE_WINDOW_DAYS, RECENT_DAYS
from app.core.files import load_yaml
from app.collectors.discovery import reddit_queries, reddit_subreddits
from app.pipeline.extract import category_signal_ok, extract_entity

CURATED_SEED_POSTS = [
    {
        "category": "transport",
        "url": "https://old.reddit.com/r/malaysia/comments/1ue2exe/commuters_on_kelana_jaya_line_can_expect_delays/",
        "fallback_text": "Commuters on the Kelana Jaya Line can expect delays.",
        "fallback_created_at": "2026-06-24T03:35:05+00:00",
        "fallback_author_handle": "MajlisPerbandaranKL",
    },
    {
        "category": "transport",
        "url": "https://old.reddit.com/r/malaysia/comments/1qv8f5x/lrt_kelana_jaya_line_having_problems_again_this/",
        "fallback_text": "LRT Kelana Jaya line having problems again this morning. This is getting too frequent.",
    },
    {
        "category": "telco_internet",
        "url": "https://old.reddit.com/r/malaysia/comments/1pahpti/unifi_down_all_week_why/",
        "fallback_text": "UNIFI down all week. Anyone in Kelantan experiencing problems with Unifi home internet? It keeps shutting off for 1-2 hours.",
    },
    {
        "category": "telco_internet",
        "url": "https://old.reddit.com/r/Bolehland/comments/1qd67kk/unifi_down_almost_24_hour_already_also_a_cat_tax/",
        "fallback_text": "Unifi down almost 24 hours already. Houses on the same road lost internet access and reports were already made.",
    },
]

SUBREDDITS = {
    "transport": ["malaysia"],
    "telco_internet": ["malaysia", "Bolehland"],
    "banking_payments": ["malaysia", "MalaysianPF"],
    "gov_portals": ["malaysia"],
    "flood_weather": ["malaysia"],
}

REDDIT_DISCOVERY_QUERIES = {
    "transport": [
        "kelana jaya line delay",
        "mrt delay",
        "gangguan lrt",
        "rapidkl kelewatan",
    ],
    "telco_internet": [
        "unifi down",
        "maxis outage",
    ],
    "banking_payments": [
        "duitnow pending",
    ],
    "gov_portals": [
        "myjpj error",
    ],
    "flood_weather": [
        "banjir kl",
    ],
}

IGNORED_QUERY_TOKENS = {
    "boleh",
    "problem",
    "issue",
    "error",
    "pending",
    "road",
    "flood",
    "delay",
    "lambat",
    "line",
    "down",
    "outage",
    "rosak",
    "internet",
    "jam",
    "tak",
}

SHORT_ENTITY_TOKENS = {"lrt", "mrt", "ktm", "mae", "kwsp"}

COMPLAINT_HINTS = {
    "down",
    "outage",
    "tak boleh",
    "rosak",
    "lambat",
    "delay",
    "pending",
    "gangguan",
    "problem",
    "issue",
    "error",
    "banjir",
}

ARTICLE_SENTENCE_HINTS = {
    "delay",
    "lambat",
    "gangguan",
    "incident",
    "technical",
    "fault",
    "brake",
    "malfunction",
    "station",
    "train",
    "tren",
}


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


def _trim_reddit_boilerplate(text: str) -> str:
    markers = [
        "a subreddit about malaysia and all things malaysian",
        "new to reddit?",
        "subreddit rules",
        "cultural exchanges",
        "meetups",
        "related social media",
    ]
    trimmed = clean_text(text)
    for marker in markers:
        idx = trimmed.lower().find(marker)
        if idx > 0:
            trimmed = trimmed[:idx].strip()
    return trimmed


def _matches_query(text: str, query: str) -> bool:
    low = text.lower()
    tokens = [
        token
        for token in query.lower().split()
        if (len(token) >= 4 or token in SHORT_ENTITY_TOKENS) and token not in IGNORED_QUERY_TOKENS
    ]
    if not tokens:
        return False
    has_query_anchor = any(re.search(r"\b" + re.escape(token) + r"\b", low) for token in tokens)
    has_complaint_signal = any(token in low for token in COMPLAINT_HINTS)
    return has_query_anchor and has_complaint_signal


def _category_prefilter(text: str, category: str) -> bool:
    entity = extract_entity(text, category)
    return category_signal_ok(text, category, entity)


def _reddit_created_at_from_node(node) -> str:
    time_el = node.select_one("time")
    return clean_text(time_el.get("datetime", "") if time_el else "")


def _extract_external_article_excerpt(url: str) -> str:
    try:
        html = fetch_html(url, timeout=12)
    except Exception:
        return ""
    soup = soup_from_html(html)
    parts: list[str] = []
    for p in soup.select("p")[:12]:
        text = clean_text(p.get_text(" ", strip=True))
        low = text.lower()
        if len(text) < 40:
            continue
        if not any(token in low for token in ARTICLE_SENTENCE_HINTS):
            continue
        parts.append(text)
        if len(parts) >= 3:
            break
    return clean_text(" ".join(parts))


def _extract_reddit_post_payload(post_url: str) -> dict[str, str]:
    try:
        html = fetch_html(post_url, timeout=10)
    except Exception:
        return {}
    soup = soup_from_html(html)
    title_el = soup.select_one("a.title") or soup.select_one("h1")
    author_el = soup.select_one("a.author")
    body_nodes = soup.select("div.thing.link div.usertext-body div.md p")[:4]
    if not body_nodes:
        body_nodes = soup.select("div.entry div.usertext-body div.md p")[:4]
    thing = soup.select_one("div.thing.link")
    linked_url = clean_text(thing.get("data-url", "") if thing else "")
    payload = {
        "title": clean_text(title_el.get_text(" ", strip=True) if title_el else ""),
        "body": _trim_reddit_boilerplate(clean_text(" ".join(node.get_text(" ", strip=True) for node in body_nodes))),
        "author_handle": clean_text(author_el.get_text(" ", strip=True) if author_el else ""),
        "created_at": _reddit_created_at_from_node(soup),
        "linked_url": linked_url,
    }
    return payload


def _curated_seed_rows() -> list[dict]:
    rows: list[dict] = []
    for seed in CURATED_SEED_POSTS:
        text = seed["fallback_text"]
        created_at = seed.get("fallback_created_at", "")
        author_handle = seed.get("fallback_author_handle", "reddit:seed")
        payload = _extract_reddit_post_payload(seed["url"])
        if payload:
            created_at = payload.get("created_at", "")
            author_handle = payload.get("author_handle") or author_handle
            body = payload.get("body", "")
            if seed["category"] == "transport" and not _category_prefilter(body, seed["category"]):
                body = _extract_external_article_excerpt(payload.get("linked_url", ""))
            if body and not _category_prefilter(body, seed["category"]):
                body = ""
            combined = clean_text(f"{payload.get('title', '')} {body}").strip()
            if combined:
                text = combined
        if not _category_prefilter(text, seed["category"]):
            continue
        if not _is_recent_enough(created_at):
            continue
        rows.append(
            {
                "source_platform": "reddit",
                "post_id": make_post_id(seed["url"]),
                "url": seed["url"],
                "author_handle": author_handle,
                "created_at": created_at,
                "raw_text": text,
                "query": "seed_url",
                "seed_category": seed["category"],
            }
        )
    return rows


def collect_reddit_sample() -> list[dict]:
    rows: list[dict] = _curated_seed_rows()
    seen_post_ids = {row["post_id"] for row in rows}
    query_groups = load_yaml("queries.yaml").get("query_groups", {})
    for category in query_groups:
        search_queries = reddit_queries(category) or REDDIT_DISCOVERY_QUERIES.get(category) or query_groups.get(category, [])[:2]
        subreddits = reddit_subreddits(category) or SUBREDDITS.get(category, ["malaysia"])
        per_search = 3 if category != "transport" else 5
        for query in search_queries:
            for subreddit in subreddits:
                url = f"https://old.reddit.com/r/{subreddit}/search/?q={quote_plus(query)}&restrict_sr=on&sort=new&t=week"
                try:
                    html = fetch_html(url)
                except Exception:
                    continue
                soup = soup_from_html(html)
                for post in soup.select("div.search-result")[:per_search]:
                    title_el = post.select_one("a.search-title")
                    meta_el = post.select_one("div.search-result-meta")
                    snippet_el = post.select_one("div.search-result-body")
                    if not title_el:
                        continue
                    title = clean_text(title_el.get_text(" ", strip=True))
                    snippet = clean_text(snippet_el.get_text(" ", strip=True) if snippet_el else "")
                    combined = clean_text(f"{title} {snippet}")
                    if not _matches_query(combined, query):
                        continue
                    if not _category_prefilter(combined, category):
                        continue
                    post_url = title_el.get("href", "")
                    author_handle = clean_text(meta_el.get_text(" ", strip=True) if meta_el else f"reddit:{subreddit}")
                    created_at = _reddit_created_at_from_node(post)
                    payload = _extract_reddit_post_payload(post_url) if post_url else {}
                    if payload:
                        title = payload.get("title", "") or title
                        body = payload.get("body", "")
                        if category == "transport" and not _category_prefilter(body, category):
                            body = _extract_external_article_excerpt(payload.get("linked_url", ""))
                        if body and not _category_prefilter(body, category):
                            body = ""
                        enriched = clean_text(f"{title} {body}").strip()
                        if enriched:
                            combined = enriched
                        author_handle = payload.get("author_handle") or author_handle
                        created_at = payload.get("created_at") or created_at
                    if not _matches_query(combined, query):
                        continue
                    if not _category_prefilter(combined, category):
                        continue
                    if not _is_recent_enough(created_at):
                        continue
                    seed = post_url or f"reddit:{query}:{title}"
                    post_id = make_post_id(seed)
                    if post_id in seen_post_ids:
                        continue
                    seen_post_ids.add(post_id)
                    rows.append(
                        {
                            "source_platform": "reddit",
                            "post_id": post_id,
                            "url": post_url,
                            "author_handle": author_handle,
                            "created_at": created_at,
                            "raw_text": combined,
                            "query": query,
                            "seed_category": category,
                        }
                    )
    return rows
