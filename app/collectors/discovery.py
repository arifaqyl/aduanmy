from __future__ import annotations

from app.core.config import settings
from app.core.files import load_yaml

_DEPTH_SLICE = {
    "minimal": 2,
    "normal": 6,
    "full": 999,
}


def _depth_limit() -> int:
    return _DEPTH_SLICE.get(settings.discovery_depth, 6)


def discovery_config() -> dict:
    return load_yaml("discovery.yaml")


def reddit_subreddits(category: str) -> list[str]:
    subs = discovery_config().get("reddit_subreddits", {}).get(category, ["malaysia"])
    return subs[: _depth_limit()] if settings.discovery_depth == "minimal" else subs


def reddit_queries(category: str) -> list[str]:
    queries = discovery_config().get("reddit_queries", {}).get(category, [])
    return queries[: _depth_limit()]


def threads_queries(category: str) -> list[str]:
    queries = discovery_config().get("threads_queries", {}).get(category, [])
    return queries[: _depth_limit()]


def threads_watchlist(category: str) -> list[dict]:
    """Primary watchlist — excludes news roles (RSS covers news)."""
    items = discovery_config().get("threads_watchlist", {}).get(category, [])
    items = [item for item in items if (item.get("role") or "commuter") != "news"]
    if settings.discovery_depth == "minimal":
        return items[:2]
    if settings.discovery_depth == "normal":
        return items[:5]
    return items


def x_queries(category: str) -> list[str]:
    queries = discovery_config().get("x_queries", {}).get(category, [])
    return queries[: _depth_limit()]


def rss_feeds() -> list[dict]:
    feeds = discovery_config().get("rss_feeds", [])
    if settings.discovery_depth == "minimal":
        return feeds[:3]
    if settings.discovery_depth == "normal":
        return feeds
    return feeds
