"""Rate-limit middleware: sliding window on hot paths."""
from __future__ import annotations

from starlette.testclient import TestClient

from app.core import rate_limit as rl
from app.core.config import settings
from app.db.session import reset_complaints
from app.main import create_app


def setup_function():
    rl.reset_rate_limits()


def test_check_rate_limit_allows_then_blocks():
    rl.reset_rate_limits()
    key = "test:search"
    for _ in range(3):
        ok, _ = rl.check_rate_limit(key, limit=3, window_seconds=60)
        assert ok is True
    ok, retry = rl.check_rate_limit(key, limit=3, window_seconds=60)
    assert ok is False
    assert retry >= 1


def test_check_rate_limit_window_expires(monkeypatch):
    rl.reset_rate_limits()
    key = "test:window"
    now = 1000.0
    for _ in range(2):
        ok, _ = rl.check_rate_limit(key, limit=2, window_seconds=10, now=now)
        assert ok is True
    ok, _ = rl.check_rate_limit(key, limit=2, window_seconds=10, now=now)
    assert ok is False
    # After window slides past the first hits, allow again.
    ok, _ = rl.check_rate_limit(key, limit=2, window_seconds=10, now=now + 11)
    assert ok is True


def test_search_rate_limit_returns_429(monkeypatch):
    reset_complaints()
    rl.reset_rate_limits()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_force", True)
    monkeypatch.setattr(settings, "auto_refresh_enabled", False)
    # Tighten search to 3/window for a fast assertion.
    monkeypatch.setattr(
        rl,
        "_RULES",
        [
            ("GET", "/api/trafficmy/search", 3, 60),
            ("*", "/api/", 1000, 60),
        ],
    )
    client = TestClient(create_app())
    codes = [client.get("/api/trafficmy/search", params={"q": "bangsar"}).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429
    blocked = client.get("/api/trafficmy/search", params={"q": "bangsar"})
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert "retry_after_seconds" in blocked.json()


def test_health_exempt_from_rate_limit(monkeypatch):
    rl.reset_rate_limits()
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_force", True)
    monkeypatch.setattr(settings, "auto_refresh_enabled", False)
    monkeypatch.setattr(
        rl,
        "_RULES",
        [("*", "/api/", 2, 60)],
    )
    client = TestClient(create_app())
    # Burn the /api/ quota on a non-exempt route first.
    assert client.get("/api/trafficmy/status").status_code in {200, 429}
    assert client.get("/api/trafficmy/status").status_code in {200, 429}
    # Third general API call should 429, but health stays open.
    client.get("/api/trafficmy/status")
    health = client.get("/api/health")
    assert health.status_code == 200


def test_rate_limit_disabled_setting(monkeypatch):
    rl.reset_rate_limits()
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(settings, "rate_limit_force", True)
    monkeypatch.setattr(settings, "auto_refresh_enabled", False)
    monkeypatch.setattr(
        rl,
        "_RULES",
        [("GET", "/api/trafficmy/search", 1, 60)],
    )
    client = TestClient(create_app())
    assert client.get("/api/trafficmy/search", params={"q": "a"}).status_code == 200
    assert client.get("/api/trafficmy/search", params={"q": "b"}).status_code == 200
