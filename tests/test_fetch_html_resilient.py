"""fetch_html resilience: retry + User-Agent rotation for transient failures."""
from __future__ import annotations

import pytest
import requests

from app.collectors import common


class _Resp:
    def __init__(self, text: str = "OK", status: int = 200) -> None:
        self.text = text
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code}", response=self)


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    # Backoff must not slow the suite.
    monkeypatch.setattr(common.time, "sleep", lambda *_a, **_k: None)


def _install_get(monkeypatch, behavior):
    """behavior: list of outcomes. Each is either an Exception to raise or a _Resp."""
    calls: list[dict] = []

    def fake_get(url, *, headers=None, timeout=None, allow_redirects=True):
        calls.append({"url": url, "headers": dict(headers or {}), "timeout": timeout})
        outcome = behavior[len(calls) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(common.requests, "get", fake_get)
    return calls


def test_retry_then_success(monkeypatch):
    calls = _install_get(monkeypatch, [
        requests.exceptions.ConnectionError("boom"),
        requests.exceptions.Timeout("slow"),
        _Resp("OK", 200),
    ])
    assert common.fetch_html("https://example.com/x") == "OK"
    assert len(calls) == 3


def test_4xx_not_retried(monkeypatch):
    calls = _install_get(monkeypatch, [_Resp("", 404)])
    with pytest.raises(requests.exceptions.HTTPError):
        common.fetch_html("https://example.com/x")
    assert len(calls) == 1


def test_429_retried_then_success(monkeypatch):
    calls = _install_get(monkeypatch, [_Resp("", 429), _Resp("OK", 200)])
    assert common.fetch_html("https://example.com/x") == "OK"
    assert len(calls) == 2


def test_5xx_exhausts_retries_then_raises(monkeypatch):
    calls = _install_get(monkeypatch, [_Resp("", 503), _Resp("", 502), _Resp("", 500)])
    with pytest.raises(requests.exceptions.HTTPError):
        common.fetch_html("https://example.com/x", max_retries=2)
    assert len(calls) == 3


def test_max_retries_zero(monkeypatch):
    calls = _install_get(monkeypatch, [requests.exceptions.ConnectionError("boom")])
    with pytest.raises(requests.exceptions.ConnectionError):
        common.fetch_html("https://example.com/x", max_retries=0)
    assert len(calls) == 1


def test_custom_ua_honored_over_rotation(monkeypatch):
    calls = _install_get(monkeypatch, [_Resp("OK", 200)])
    common.fetch_html("https://example.com/x", headers={"User-Agent": "CustomUA", "X-Test": "1"})
    assert calls[0]["headers"]["User-Agent"] == "CustomUA"
    assert calls[0]["headers"]["X-Test"] == "1"


def test_default_rotates_ua_on_retry(monkeypatch):
    calls = _install_get(monkeypatch, [
        requests.exceptions.ConnectionError("boom"),
        _Resp("OK", 200),
    ])
    common.fetch_html("https://example.com/x")
    uas = [c["headers"]["User-Agent"] for c in calls]
    assert uas[0] in common.USER_AGENTS
    assert uas[1] in common.USER_AGENTS
    assert uas[0] != uas[1]
