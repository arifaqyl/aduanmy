"""In-memory sliding-window rate limit for hot API paths.

No external deps. Per-process only (fine for a single uvicorn worker; multi-worker
deploys get soft per-worker limits, which is enough to blunt a viral scrape spike
against SQLite). Disable with ADUANMY_RATE_LIMIT_ENABLED=false.

Under pytest the middleware is auto-skipped (the suite issues hundreds of API
calls from one IP). Tests that need coverage set settings.rate_limit_force=True
and call reset_rate_limits().
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# Most specific match wins (checked in order).
_RULES: list[tuple[str, str, int, int]] = [
    # method, path_prefix, limit, window
    ("POST", "/api/refresh", 5, 60),
    ("GET", "/api/trafficmy/search", 30, 60),
    ("GET", "/api/trafficmy/export", 10, 60),
    ("GET", "/api/trafficmy/gps-gaps", 30, 60),
    ("GET", "/api/trafficmy/source-health", 30, 60),
    ("*", "/api/", 180, 60),
]

_EXEMPT_PREFIXES = (
    "/api/health",
    "/static",
)
_EXEMPT_EXACT = {
    "/",
    "/methodology",
    "/developers",
    "/status",
    "/embed",
    "/manifest.webmanifest",
    "/sw.js",
}

_lock = threading.Lock()
_buckets: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    """Clear all buckets — for tests."""
    with _lock:
        _buckets.clear()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or "unknown"
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _match_rule(method: str, path: str) -> tuple[int, int] | None:
    for rule_method, prefix, limit, window in _RULES:
        if rule_method not in ("*", method):
            continue
        if path == prefix or path.startswith(prefix):
            return limit, window
    return None


def _is_exempt(method: str, path: str) -> bool:
    if method == "OPTIONS":
        return True
    if path in _EXEMPT_EXACT:
        return True
    return any(path == p or path.startswith(p) for p in _EXEMPT_PREFIXES)


def _bucket_key(ip: str, method: str, path: str) -> str:
    if path.startswith("/api/trafficmy/search"):
        return f"{ip}:GET:search"
    if path.startswith("/api/trafficmy/export"):
        return f"{ip}:GET:export"
    if path.rstrip("/").endswith("/refresh") and method == "POST":
        return f"{ip}:POST:refresh"
    if path.startswith("/api/"):
        return f"{ip}:API"
    return f"{ip}:{method}:{path}"


def check_rate_limit(
    key: str, *, limit: int, window_seconds: int, now: float | None = None
) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds). Pure helper for tests."""
    now = time.monotonic() if now is None else now
    cutoff = now - window_seconds
    with _lock:
        bucket = _buckets[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= limit:
            retry = max(1, int(window_seconds - (now - bucket[0])) + 1)
            return False, retry
        bucket.append(now)
        return True, 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        from app.core.config import settings

        if not settings.rate_limit_enabled:
            return await call_next(request)
        # Suite issues hundreds of calls from one IP — skip unless a test forces it.
        if os.environ.get("PYTEST_CURRENT_TEST") and not settings.rate_limit_force:
            return await call_next(request)

        method = request.method.upper()
        path = request.url.path
        if _is_exempt(method, path):
            return await call_next(request)

        rule = _match_rule(method, path)
        if rule is None:
            return await call_next(request)

        limit, window = rule
        key = _bucket_key(_client_ip(request), method, path)
        allowed, retry_after = check_rate_limit(key, limit=limit, window_seconds=window)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Slow down and retry shortly.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)
