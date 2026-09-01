"""Collector-health paging.

The failure this guards against: every collector returns zero rows, nothing
raises, and the board renders a clean "no rider reports today" that looks
identical to a genuinely quiet day. That state went unnoticed for two months.
"""
from __future__ import annotations

import pytest

from app.db.session import connect, init_db
from app.services import telegram_alerts


@pytest.fixture
def ops(monkeypatch):
    """Captured Telegram sends. DB isolation comes from the autouse
    `isolated_test_db` fixture in conftest, which swaps settings.db_path."""
    monkeypatch.setattr(telegram_alerts.settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(telegram_alerts.settings, "telegram_ops_chat_id", "999")

    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        telegram_alerts, "send_message", lambda chat, text: (sent.append((chat, text)), True)[1]
    )
    init_db()
    return sent


def _health(monkeypatch, items):
    import app.services.source_health_service as shs

    monkeypatch.setattr(shs, "get_source_health", lambda: items)


def _src(name, bad, empties=0, last=None):
    return {
        "source": name,
        "needs_attention": bad,
        "consecutive_empty_runs": empties,
        "last_nonempty_at": last,
    }


def test_pages_once_when_a_collector_goes_quiet(ops, monkeypatch):
    _health(monkeypatch, [_src("threads", True, 3, "2026-07-01T09:41:02Z")])

    first = telegram_alerts.check_source_health_and_alert()
    assert first["sent"] == 1
    assert "threads" in ops[0][1]
    assert "3" in ops[0][1]

    # Still broken on the next ingest: must stay silent, not page every 15 min.
    second = telegram_alerts.check_source_health_and_alert()
    assert second["sent"] == 0
    assert len(ops) == 1


def test_pages_on_recovery(ops, monkeypatch):
    _health(monkeypatch, [_src("threads", True, 3)])
    telegram_alerts.check_source_health_and_alert()
    assert len(ops) == 1

    _health(monkeypatch, [_src("threads", False, 0, "2026-09-02T01:00:00Z")])
    out = telegram_alerts.check_source_health_and_alert()
    assert out["sent"] == 1
    assert "again" in ops[1][1].lower()


def test_healthy_collector_never_pages(ops, monkeypatch):
    _health(monkeypatch, [_src("rss", False, 0, "2026-09-02T01:00:00Z")])
    out = telegram_alerts.check_source_health_and_alert()
    assert out["sent"] == 0
    assert ops == []


def test_each_collector_is_tracked_independently(ops, monkeypatch):
    _health(monkeypatch, [_src("threads", True, 4), _src("rss", False, 0)])
    telegram_alerts.check_source_health_and_alert()
    assert len(ops) == 1

    # rss now breaks too — that is a new transition and must page.
    _health(monkeypatch, [_src("threads", True, 5), _src("rss", True, 3)])
    out = telegram_alerts.check_source_health_and_alert()
    assert out["sent"] == 1
    assert "rss" in ops[1][1]


def test_no_ops_chat_configured_is_a_safe_noop(ops, monkeypatch):
    monkeypatch.setattr(telegram_alerts.settings, "telegram_ops_chat_id", "")
    _health(monkeypatch, [_src("threads", True, 9)])
    out = telegram_alerts.check_source_health_and_alert()
    assert out["sent"] == 0
    assert out["skipped"] == "no_token_or_ops_chat"
    assert ops == []


def test_alerting_failure_never_breaks_ingest(ops, monkeypatch):
    import app.services.source_health_service as shs

    def boom():
        raise RuntimeError("db exploded")

    monkeypatch.setattr(shs, "get_source_health", boom)
    out = telegram_alerts.check_source_health_and_alert()
    assert out["error"] is True  # swallowed, reported, not raised


def test_state_persists_across_calls(ops, monkeypatch):
    _health(monkeypatch, [_src("threads", True, 3)])
    telegram_alerts.check_source_health_and_alert()

    with connect() as conn:
        row = conn.execute(
            "SELECT source, needs_attention FROM source_health_alerts WHERE source = 'threads'"
        ).fetchone()
    assert row is not None
    assert bool(row["needs_attention"]) is True
