"""TrafficMY revamp batch 2: re-enable X for trusted operator handles via syndication."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.collectors.x import client as x_client
from app.collectors.x.client import collect_x_sample, collect_x_trusted_sample
from app.core.config import settings
from app.services import ingest_service


SNOWFLAKE_EPOCH_MS = 1288834974657


def _snowflake(dt: datetime, low: int = 1) -> int:
    ts_ms = int(dt.timestamp() * 1000)
    return ((ts_ms - SNOWFLAKE_EPOCH_MS) << 22) | (low & 0x003FFFFF)


def _seed(profile_url: str = "https://x.com/askrapidkl") -> dict:
    return {"x": [{"category": "transport", "url": profile_url, "discover_profile": True}]}


def _install_fetch(monkeypatch, *, recent_id: int, old_id: int, tweet_text: str, tweet_for_old: str = "") -> list[str]:
    """Mock fetch_html to serve syndication HTML + fxtwitter JSON. Records called URLs."""
    called: list[str] = []

    def fake_fetch_html(url, *, headers=None, timeout=20, max_retries=2):
        called.append(url)
        if "syndication.twitter.com" in url:
            return f'<a href="/askrapidkl/status/{recent_id}">x</a> <a href="/askrapidkl/status/{old_id}">x</a>'
        if "api.fxtwitter.com" in url:
            import json
            text = tweet_text if str(recent_id) in url else tweet_for_old
            return json.dumps({"tweet": {"text": text}}) if text else "{}"
        return ""

    monkeypatch.setattr(x_client, "fetch_html", fake_fetch_html)
    return called


def test_trusted_collects_recent_alert_only(monkeypatch):
    now = datetime.now(UTC)
    recent_id = _snowflake(now - timedelta(minutes=10))
    old_id = _snowflake(now - timedelta(days=40))
    monkeypatch.setattr(x_client, "load_yaml", lambda _name: _seed())
    _install_fetch(monkeypatch, recent_id=recent_id, old_id=old_id,
                   tweet_text="LRT Kelana Jaya line delay — help and rescue mobilising")

    rows = collect_x_trusted_sample()

    assert len(rows) == 1
    row = rows[0]
    assert row["source_platform"] == "x"
    assert row["author_handle"] == "askrapidkl"
    assert row["query"] == "trusted_profile_syndication"
    assert str(recent_id) in row["url"]
    assert "delay" in row["raw_text"]


def test_trusted_filters_non_incident_text(monkeypatch):
    now = datetime.now(UTC)
    recent_id = _snowflake(now - timedelta(minutes=10))
    old_id = _snowflake(now - timedelta(days=40))
    monkeypatch.setattr(x_client, "load_yaml", lambda _name: _seed())
    _install_fetch(monkeypatch, recent_id=recent_id, old_id=old_id,
                   tweet_text="Terima kasih atas maklum balas anda, kami akan balas notis anda.")

    rows = collect_x_trusted_sample()
    assert rows == []


def test_trusted_skips_when_fxtwitter_empty(monkeypatch):
    now = datetime.now(UTC)
    recent_id = _snowflake(now - timedelta(minutes=10))
    old_id = _snowflake(now - timedelta(days=40))
    monkeypatch.setattr(x_client, "load_yaml", lambda _name: _seed())
    _install_fetch(monkeypatch, recent_id=recent_id, old_id=old_id, tweet_text="")

    rows = collect_x_trusted_sample()
    assert rows == []


def test_trusted_only_uses_syndication_and_fxtwitter_not_bing_or_playwright(monkeypatch):
    now = datetime.now(UTC)
    recent_id = _snowflake(now - timedelta(minutes=10))
    old_id = _snowflake(now - timedelta(days=40))
    monkeypatch.setattr(x_client, "load_yaml", lambda _name: _seed())
    called = _install_fetch(monkeypatch, recent_id=recent_id, old_id=old_id,
                            tweet_text="LRT Kelana Jaya line delay — help and rescue mobilising")

    collect_x_trusted_sample()
    assert any("syndication.twitter.com" in u for u in called)
    assert any("api.fxtwitter.com" in u for u in called)
    assert not any("bing.com" in u for u in called)


def test_collectors_picks_trusted_when_auto_off(monkeypatch):
    monkeypatch.setattr(settings, "x_auto_collect_enabled", False)
    monkeypatch.setattr(settings, "x_trusted_handles_enabled", True)
    collectors = ingest_service._collectors()
    assert collectors["x"] is collect_x_trusted_sample


def test_collectors_picks_full_when_auto_on(monkeypatch):
    monkeypatch.setattr(settings, "x_auto_collect_enabled", True)
    monkeypatch.setattr(settings, "x_trusted_handles_enabled", True)
    collectors = ingest_service._collectors()
    assert collectors["x"] is collect_x_sample


def test_collectors_omits_x_when_both_off(monkeypatch):
    monkeypatch.setattr(settings, "x_auto_collect_enabled", False)
    monkeypatch.setattr(settings, "x_trusted_handles_enabled", False)
    collectors = ingest_service._collectors()
    assert "x" not in collectors


def test_collector_due_x_disabled_when_both_off(monkeypatch):
    monkeypatch.setattr(settings, "x_auto_collect_enabled", False)
    monkeypatch.setattr(settings, "x_trusted_handles_enabled", False)
    due, reason = ingest_service._collector_due("x", respect_cadence=False)
    assert due is False
    assert reason == "disabled_until_authenticated"


def test_collector_due_x_enabled_when_trusted_only(monkeypatch):
    monkeypatch.setattr(settings, "x_auto_collect_enabled", False)
    monkeypatch.setattr(settings, "x_trusted_handles_enabled", True)
    due, _reason = ingest_service._collector_due("x", respect_cadence=False)
    assert due is True
