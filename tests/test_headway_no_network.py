"""A board render must never block on data.gov.my.

This property was violated once: scheduled_headway() on the board path called
download_static() whenever the cache was cold, and a test suite building
boards hammered the endpoint into a 429. Reads are now cache-only; only
warm_headways(), called from the scheduler, may download.
"""
from __future__ import annotations

import pytest

from app.services import headway_service as H


@pytest.fixture(autouse=True)
def cold_cache():
    H._cache["key"] = None
    H._cache["bands"] = {}
    yield
    H._cache["key"] = None
    H._cache["bands"] = {}


def test_load_headways_never_downloads(monkeypatch):
    """With an empty cache dir (the isolated test data_dir), reads return {}
    and must not reach for the network."""
    import app.collectors.gtfs.static_client as sc

    def boom(*a, **k):
        raise AssertionError("load_headways must not call download_static")

    monkeypatch.setattr(sc, "download_static", boom)
    assert H.load_headways() == {}
    assert H.scheduled_headway("kelana-jaya") is None
    assert H.deviation("kelana-jaya", 20) is None


def test_warm_headways_is_the_only_downloader(monkeypatch):
    import app.collectors.gtfs.static_client as sc

    calls = {"n": 0}

    def fake_download(network, *, force=False):
        calls["n"] += 1
        raise RuntimeError("offline")   # exercise the failure branch too

    monkeypatch.setattr(sc, "download_static", fake_download)
    assert H.warm_headways() == 0       # offline + cold cache -> 0 lines, no raise
    assert calls["n"] == 1


def test_board_build_with_cold_cache_degrades_to_none_not_error(monkeypatch):
    """The board path must survive a cold cache: headway/deviation are None."""
    import app.collectors.gtfs.static_client as sc

    monkeypatch.setattr(sc, "download_static",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("network on board path")))
    from app.services.line_status_service import get_line_status_board

    board = get_line_status_board()
    assert board["lines"]                      # board still renders
    for line in board["lines"]:
        assert line["headway"] is None
        assert line["deviation"] is None
