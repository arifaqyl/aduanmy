"""Batch 1 revamp: search, export, prod refresh hardening, scheduler single-worker guard."""
from __future__ import annotations

import time
from datetime import timedelta
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.core.freshness import myt_day_start
from app.db.session import reset_complaints, upsert_complaints
from app.main import create_app
from app.schemas.complaint import ComplaintSchema


def _today_iso(hours: int = 0, minutes: int = 0) -> str:
    return (myt_day_start() + timedelta(hours=hours, minutes=minutes)).isoformat().replace("+00:00", "Z")


def _seed_search_rows() -> None:
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="s1",
                url="https://example.com/s1",
                author_handle="rider1",
                created_at=_today_iso(8),
                raw_text="MRT Kelana Jaya line delay at Bangsar, train stuck",
                normalized_text="mrt kelana jaya line delay at bangsar train stuck",
                category="transport",
                subcategory="delay",
                entity="kelana jaya line",
                location="bangsar",
                severity="medium",
                confidence=0.6,
                cluster_id="cl-bangsar-delay",
            ),
            ComplaintSchema(
                source_platform="reddit",
                post_id="s2",
                url="https://example.com/s2",
                author_handle="rider2",
                created_at=_today_iso(9),
                raw_text="KTM Komuter Serdang breakdown this morning",
                normalized_text="ktm komuter serdang breakdown this morning",
                category="transport",
                subcategory="breakdown",
                entity="ktm komuter",
                location="serdang",
                severity="high",
                confidence=0.7,
                cluster_id="cl-serdang-breakdown",
            ),
        ]
    )


def test_search_returns_matching_clusters_without_raw_text():
    _seed_search_rows()
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/search", params={"q": "bangsar"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    items = payload["items"]
    assert any(item["cluster_id"] == "cl-bangsar-delay" for item in items)
    match = next(item for item in items if item["cluster_id"] == "cl-bangsar-delay")
    assert match["matched_signals"] >= 1
    # Trust model: no raw signal text or author handles leaked via search.
    assert "raw_text" not in match
    assert "author_handles" not in match


def test_search_matches_entity_and_location_fields():
    _seed_search_rows()
    client = TestClient(create_app())
    by_entity = client.get("/api/trafficmy/search", params={"q": "kelana jaya line"})
    assert by_entity.status_code == 200
    assert any(item["cluster_id"] == "cl-bangsar-delay" for item in by_entity.json()["items"])

    by_location = client.get("/api/trafficmy/search", params={"q": "serdang"})
    assert any(item["cluster_id"] == "cl-serdang-breakdown" for item in by_location.json()["items"])


def test_search_rejects_short_and_empty_queries():
    _seed_search_rows()
    client = TestClient(create_app())
    for q in ["", "a"]:
        response = client.get("/api/trafficmy/search", params={"q": q})
        assert response.status_code == 200
        assert response.json()["total"] == 0
        assert response.json()["items"] == []


def test_export_json_returns_signals_payload():
    _seed_search_rows()
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/export", params={"format": "json"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "TrafficMY"
    assert "signals" in payload
    assert isinstance(payload["signals"], list)


def test_export_csv_has_header_and_rows():
    _seed_search_rows()
    client = TestClient(create_app())
    response = client.get("/api/trafficmy/export", params={"format": "csv"})
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "attachment" in response.headers.get("content-disposition", "")
    body = response.text
    assert body.startswith("id,line_id,entity,location,issue,severity,when,last_seen_at,confidence_band,corroborated_by_official,sources,glance_line")
    # At least one data row beyond the header.
    assert body.count("\n") >= 2


def test_refresh_denied_in_production_when_api_key_empty(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.env", "production")
    monkeypatch.setattr("app.core.config.settings.refresh_api_key", "")
    monkeypatch.setattr("app.core.config.settings.auto_refresh_enabled", False)
    client = TestClient(create_app())
    response = client.post("/api/refresh?sync=true")
    assert response.status_code == 401


def test_refresh_allowed_in_production_with_matching_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.env", "production")
    monkeypatch.setattr("app.core.config.settings.refresh_api_key", "secret-key")
    monkeypatch.setattr("app.core.config.settings.auto_refresh_enabled", False)
    monkeypatch.setattr(
        "app.api.routes.incidents.run_full_now",
        lambda: {"written": 1, "threads": 1},
    )
    client = TestClient(create_app())
    response = client.post("/api/refresh?sync=true", headers={"X-API-Key": "secret-key"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_scheduler_lock_dev_always_acquires(monkeypatch, tmp_path):
    import app.services.scheduler_service as sched

    monkeypatch.setattr("app.core.config.settings.env", "dev")
    monkeypatch.setattr("app.core.config.settings.data_dir", str(tmp_path))
    sched._scheduler_lock_owner = False
    sched._scheduler_lock_fd = None
    assert sched._try_acquire_scheduler_lock() is True
    # Dev short-circuits and must not create a lockfile.
    assert not (tmp_path / ".scheduler.lock").exists()


def test_scheduler_lock_prod_second_worker_defers(monkeypatch, tmp_path):
    import app.services.scheduler_service as sched

    monkeypatch.setattr("app.core.config.settings.env", "production")
    monkeypatch.setattr("app.core.config.settings.data_dir", str(tmp_path))
    monkeypatch.setattr("app.core.config.settings.full_refresh_interval_seconds", 900)
    sched._scheduler_lock_owner = False
    sched._scheduler_lock_fd = None
    assert sched._try_acquire_scheduler_lock() is True
    assert sched._scheduler_lock_owner is True
    # A second worker (same dir, lock held) must defer.
    held_fd = sched._scheduler_lock_fd
    sched._scheduler_lock_owner = False
    sched._scheduler_lock_fd = None
    assert sched._try_acquire_scheduler_lock() is False
    if held_fd is not None:
        import os

        os.close(held_fd)


def test_scheduler_lock_prod_steals_stale_lock(monkeypatch, tmp_path):
    import app.services.scheduler_service as sched

    monkeypatch.setattr("app.core.config.settings.env", "production")
    monkeypatch.setattr("app.core.config.settings.data_dir", str(tmp_path))
    monkeypatch.setattr("app.core.config.settings.full_refresh_interval_seconds", 900)
    lock = tmp_path / ".scheduler.lock"
    lock.write_text("99999\n0\n")
    # Backdate beyond the fallback age window (fcntl path does not need this;
    # fallback steals after 120s with no live flock holder).
    stale = time.time() - 180
    import os

    os.utime(str(lock), (stale, stale))
    sched._scheduler_lock_owner = False
    sched._scheduler_lock_fd = None
    assert sched._try_acquire_scheduler_lock() is True
    if sched._scheduler_lock_fd is not None:
        os.close(sched._scheduler_lock_fd)
        sched._scheduler_lock_fd = None
