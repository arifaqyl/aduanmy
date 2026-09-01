"""Reddit application-only OAuth lane.

Guards the failure that took the old lane down silently: old.reddit.com began
answering scrapes with a login interstitial, returning HTTP 200 and zero rows
without raising, so the board went quiet and nothing reported why.
"""
from __future__ import annotations

import time

import pytest

from app.collectors.reddit import oauth


@pytest.fixture(autouse=True)
def reset_token():
    oauth._token["value"] = None
    oauth._token["expires_at"] = 0.0
    yield
    oauth._token["value"] = None
    oauth._token["expires_at"] = 0.0


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setattr(oauth.settings, "reddit_client_id", "cid")
    monkeypatch.setattr(oauth.settings, "reddit_client_secret", "csec")


class FakeResp:
    def __init__(self, payload=None, status=200):
        self._payload = payload if payload is not None else {}
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _listing(children):
    return {"data": {"children": [{"data": d} for d in children]}}


def _post(**over):
    d = {
        "id": "abc123",
        "title": "LRT Kelana Jaya stuck at Bangsar",
        "selftext": "waited 20 minutes, no announcement",
        "permalink": "/r/malaysia/comments/abc123/x/",
        "author": "someone",
        "created_utc": time.time() - 3600,
        "subreddit": "malaysia",
        "stickied": False,
    }
    d.update(over)
    return d


def test_unconfigured_is_reported_not_silently_empty():
    assert oauth.configured() is False
    assert oauth.health() == {"ok": False, "reason": "unconfigured"}


def test_search_returns_rows(creds, monkeypatch):
    monkeypatch.setattr(oauth.requests, "post",
                        lambda *a, **k: FakeResp({"access_token": "t", "expires_in": 3600}))
    monkeypatch.setattr(oauth.requests, "get",
                        lambda *a, **k: FakeResp(_listing([_post()])))

    rows = oauth.search("malaysia", "lrt delay")
    assert len(rows) == 1
    r = rows[0]
    assert r["source_platform"] == "reddit"
    assert r["post_id"] == "abc123"
    assert "Kelana Jaya" in r["raw_text"]
    assert r["url"].startswith("https://www.reddit.com/r/malaysia/")
    assert r["created_at"].endswith("Z")


def test_search_requests_recency_not_relevance(creds, monkeypatch):
    """Reddit defaults to relevance ranking. That default is what filled the old
    news lane with years-old posts, so sort=new must be explicit."""
    seen = {}
    monkeypatch.setattr(oauth.requests, "post",
                        lambda *a, **k: FakeResp({"access_token": "t", "expires_in": 3600}))

    def fake_get(url, params=None, **k):
        seen.update(params or {})
        return FakeResp(_listing([]))

    monkeypatch.setattr(oauth.requests, "get", fake_get)
    oauth.search("malaysia", "lrt delay")
    assert seen["sort"] == "new"
    assert seen["restrict_sr"] == 1


def test_stickied_and_removed_posts_are_skipped(creds, monkeypatch):
    monkeypatch.setattr(oauth.requests, "post",
                        lambda *a, **k: FakeResp({"access_token": "t", "expires_in": 3600}))
    monkeypatch.setattr(oauth.requests, "get", lambda *a, **k: FakeResp(_listing([
        _post(id="s1", stickied=True),
        _post(id="r1", removed_by_category="moderator"),
        _post(id="ok1"),
    ])))
    rows = oauth.search("malaysia", "q")
    assert [r["post_id"] for r in rows] == ["ok1"]


def test_post_without_a_timestamp_is_dropped(creds, monkeypatch):
    """No created_utc means the freshness gate cannot judge it, and an undated
    row is exactly how stale content used to reach a board that claims today."""
    monkeypatch.setattr(oauth.requests, "post",
                        lambda *a, **k: FakeResp({"access_token": "t", "expires_in": 3600}))
    monkeypatch.setattr(oauth.requests, "get",
                        lambda *a, **k: FakeResp(_listing([_post(created_utc=None)])))
    assert oauth.search("malaysia", "q") == []


def test_token_is_reused_then_refreshed(creds, monkeypatch):
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        return FakeResp({"access_token": f"t{calls['n']}", "expires_in": 3600})

    monkeypatch.setattr(oauth.requests, "post", fake_post)
    assert oauth._access_token() == "t1"
    assert oauth._access_token() == "t1"      # cached
    assert calls["n"] == 1

    oauth._token["expires_at"] = time.time() - 1   # force expiry
    assert oauth._access_token() == "t2"
    assert calls["n"] == 2


def test_401_clears_the_token_so_the_next_call_refreshes(creds, monkeypatch):
    monkeypatch.setattr(oauth.requests, "post",
                        lambda *a, **k: FakeResp({"access_token": "t", "expires_in": 3600}))
    monkeypatch.setattr(oauth.requests, "get", lambda *a, **k: FakeResp({}, status=401))
    assert oauth.search("malaysia", "q") == []
    assert oauth._token["value"] is None


def test_network_failure_returns_empty_never_raises(creds, monkeypatch):
    import requests as rq

    def boom(*a, **k):
        raise rq.ConnectionError("no route")

    monkeypatch.setattr(oauth.requests, "post", boom)
    assert oauth._access_token() is None
    assert oauth.search("malaysia", "q") == []
    assert oauth.health()["ok"] is False


def test_health_distinguishes_empty_from_broken(creds, monkeypatch):
    monkeypatch.setattr(oauth.requests, "post",
                        lambda *a, **k: FakeResp({"access_token": "t", "expires_in": 3600}))
    monkeypatch.setattr(oauth.requests, "get", lambda *a, **k: FakeResp(_listing([])))
    assert oauth.health() == {"ok": False, "reason": "empty"}

    monkeypatch.setattr(oauth.requests, "get", lambda *a, **k: FakeResp(_listing([_post()])))
    assert oauth.health() == {"ok": True, "reason": "ok"}
