"""TrafficMY source-health endpoint: per-collector health + primary-degraded warning."""
from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.db.session import reset_complaints
from app.main import create_app
from app.services import status_service


def _set_ingest(monkeypatch, sources: dict) -> None:
    monkeypatch.setattr(
        status_service,
        "_latest_ingest_summary",
        lambda: {"sources": sources, "snapshot_updated_at": ""},
    )


@pytest.fixture(autouse=True)
def _clean_db():
    reset_complaints()


def test_source_health_primary_degraded(monkeypatch):
    _set_ingest(
        monkeypatch,
        {
            "threads": {"status": "failed", "error": "TimeoutError: 90s", "row_count": 0,
                        "finished_at": "2026-07-24T10:00:00Z", "duration_seconds": 90},
            "reddit": {"status": "healthy", "error": "", "row_count": 5,
                       "finished_at": "2026-07-24T10:00:00Z", "duration_seconds": 2},
        },
    )
    monkeypatch.setattr(
        "app.collectors.threads.session.session_status",
        lambda **_k: {
            "available": True,
            "updated_at": "2026-07-24T09:00:00+00:00",
            "age_hours": 1.0,
            "stale": False,
            "stale_after_days": 7,
        },
    )
    client = TestClient(create_app())
    res = client.get("/api/trafficmy/source-health")
    assert res.status_code == 200
    payload = res.json()
    assert payload["primary_source"] == "threads"
    assert payload["primary_degraded"] is True
    assert payload["degraded_count"] == 1
    assert "Threads collector" in payload["warning"]
    threads = next(i for i in payload["items"] if i["source"] == "threads")
    assert threads["degraded"] is True
    assert threads["status"] == "failed"
    assert threads["error"] == "TimeoutError: 90s"
    reddit = next(i for i in payload["items"] if i["source"] == "reddit")
    assert reddit["degraded"] is False


def test_source_health_all_healthy(monkeypatch):
    _set_ingest(
        monkeypatch,
        {
            "threads": {"status": "healthy", "row_count": 12, "error": "",
                        "finished_at": "2026-07-24T10:00:00Z", "duration_seconds": 3},
            "official": {"status": "healthy", "row_count": 2, "error": "",
                         "finished_at": "2026-07-24T10:00:00Z", "duration_seconds": 1},
        },
    )
    monkeypatch.setattr(
        "app.collectors.threads.session.session_status",
        lambda **_k: {
            "available": True,
            "updated_at": "2026-07-24T09:00:00+00:00",
            "age_hours": 1.0,
            "stale": False,
            "stale_after_days": 7,
        },
    )
    client = TestClient(create_app())
    res = client.get("/api/trafficmy/source-health")
    assert res.status_code == 200
    payload = res.json()
    assert payload["primary_degraded"] is False
    assert payload["degraded_count"] == 0
    assert payload["warning"] == ""
    assert payload["session"]["stale"] is False
    assert all(not i["degraded"] for i in payload["items"])


def test_source_health_warns_on_stale_session(monkeypatch):
    _set_ingest(
        monkeypatch,
        {
            "threads": {"status": "healthy", "row_count": 2, "error": "",
                        "finished_at": "2026-07-24T10:00:00Z", "duration_seconds": 3},
        },
    )
    monkeypatch.setattr(
        "app.collectors.threads.session.session_status",
        lambda **_k: {
            "available": True,
            "updated_at": "2026-07-11T11:41:46+00:00",
            "age_hours": 312.0,
            "stale": True,
            "stale_after_days": 7,
        },
    )
    client = TestClient(create_app())
    res = client.get("/api/trafficmy/source-health")
    payload = res.json()
    assert payload["primary_degraded"] is False
    assert payload["session"]["stale"] is True
    assert "stale" in payload["warning"].lower()
    assert payload["session"]["age_hours"] == 312.0


def test_source_health_empty_counts_as_degraded(monkeypatch):
    _set_ingest(
        monkeypatch,
        {"threads": {"status": "empty", "row_count": 0, "error": "",
                     "finished_at": "2026-07-24T10:00:00Z", "duration_seconds": 1}},
    )
    monkeypatch.setattr(
        "app.collectors.threads.session.session_status",
        lambda **_k: {
            "available": True,
            "updated_at": "2026-07-24T09:00:00+00:00",
            "age_hours": 1.0,
            "stale": False,
            "stale_after_days": 7,
        },
    )
    client = TestClient(create_app())
    res = client.get("/api/trafficmy/source-health")
    payload = res.json()
    assert payload["primary_degraded"] is True
    threads = next(i for i in payload["items"] if i["source"] == "threads")
    assert threads["degraded"] is True
    assert threads["status"] == "empty"


def test_source_health_no_sources(monkeypatch):
    _set_ingest(monkeypatch, {})
    monkeypatch.setattr(
        "app.collectors.threads.session.session_status",
        lambda **_k: {
            "available": False,
            "updated_at": None,
            "age_hours": None,
            "stale": False,
            "stale_after_days": 7,
        },
    )
    client = TestClient(create_app())
    res = client.get("/api/trafficmy/source-health")
    assert res.status_code == 200
    payload = res.json()
    assert payload["primary_degraded"] is False
    assert payload["items"] == []
    assert payload["session"]["missing"] is True
    assert "session" in payload["warning"].lower()