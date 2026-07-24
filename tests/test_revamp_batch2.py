"""Batch 2 revamp: GTFS-RT 'GPS gap' layer — stale-only prune + gps-gaps endpoint."""
from __future__ import annotations

from datetime import timedelta

from starlette.testclient import TestClient

from app.core.freshness import myt_day_start
from app.db.session import reset_complaints, upsert_complaints
from app.main import create_app
from app.schemas.complaint import ComplaintSchema
from app.services.ingest_service import prune_gtfs_rt_complaints


def _today_iso(hours: int = 6, minutes: int = 0) -> str:
    return (myt_day_start() + timedelta(hours=hours, minutes=minutes)).isoformat().replace("+00:00", "Z")


def _stale_iso(days_ago: int = 2, hours: int = 6) -> str:
    return (myt_day_start() - timedelta(days=days_ago - 1) + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def _gtfs_row(post_id: str, created_at: str, entity: str = "772", location: str = "Pasar Seni") -> ComplaintSchema:
    return ComplaintSchema(
        source_platform="gtfs_rt",
        post_id=post_id,
        url="https://example.com/" + post_id,
        author_handle="gtfs:rapid-bus-kl",
        created_at=created_at,
        raw_text=f"GTFS anomaly route {entity} no active vehicles",
        normalized_text=f"gtfs anomaly route {entity} no active vehicles",
        detected_language_mix="en",
        category="transport",
        entity=entity,
        location=location,
        severity="medium",
        confidence=0.65,
        cluster_id=f"transport:{entity}:{location}",
    )


def test_prune_gtfs_rt_keeps_today_and_prunes_stale():
    reset_complaints()
    upsert_complaints(
        [
            _gtfs_row("g-today", _today_iso(6, 30)),
            _gtfs_row("g-stale", _stale_iso(2, 6), entity="773", location="Bukit Bintang"),
        ]
    )

    pruned = prune_gtfs_rt_complaints()

    assert pruned == 1
    from app.db.session import connect

    with connect() as conn:
        remaining = {row["post_id"] for row in conn.execute(
            "SELECT post_id FROM complaints WHERE source_platform = 'gtfs_rt'"
        ).fetchall()}
    assert remaining == {"g-today"}


def test_prune_gtfs_rt_no_rows_returns_zero():
    reset_complaints()
    assert prune_gtfs_rt_complaints() == 0


def test_prune_gtfs_rt_does_not_touch_social_rows():
    reset_complaints()
    upsert_complaints(
        [
            _gtfs_row("g-stale", _stale_iso(2, 6)),
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/t1",
                author_handle="rider1",
                created_at=_stale_iso(2, 6),
                raw_text="KTM Serdang breakdown",
                normalized_text="ktm serdang breakdown",
                detected_language_mix="en",
                category="transport",
                entity="KTM Komuter",
                location="Serdang",
                severity="high",
                confidence=0.7,
                cluster_id="transport:KTM Komuter:Serdang:breakdown",
            ),
        ]
    )

    pruned = prune_gtfs_rt_complaints()
    assert pruned == 1
    from app.db.session import connect

    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM complaints WHERE source_platform = 'threads'").fetchone()[0] == 1


def test_gps_gaps_endpoint_returns_today_hints_with_disclaimer():
    reset_complaints()
    upsert_complaints([_gtfs_row("g-today", _today_iso(6, 30))])
    client = TestClient(create_app())

    response = client.get("/api/trafficmy/gps-gaps")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "TrafficMY"
    assert payload["layer"] == "gps_gaps"
    assert payload["confidence"] == "low"
    assert "GPS/feed gap" in payload["disclaimer"]
    assert payload["count"] >= 1
    assert any(item["sources"] == "gtfs_rt" for item in payload["items"])


def test_gps_gaps_excludes_social_clusters():
    reset_complaints()
    upsert_complaints(
        [
            _gtfs_row("g-today", _today_iso(6, 30)),
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/t1",
                author_handle="rider1",
                created_at=_today_iso(8, 0),
                raw_text="Kelana Jaya LRT delay stuck at Bangsar",
                normalized_text="kelana jaya lrt delay stuck at bangsar",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Bangsar",
                severity="high",
                confidence=0.8,
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            ),
        ]
    )
    client = TestClient(create_app())

    response = client.get("/api/trafficmy/gps-gaps")
    assert response.status_code == 200
    payload = response.json()
    sources = {item["sources"] for item in payload["items"]}
    assert "gtfs_rt" in sources
    assert "threads" not in sources


def test_gps_gaps_respects_limit():
    reset_complaints()
    upsert_complaints(
        [
            _gtfs_row(f"g{i}", _today_iso(6, i), entity=str(700 + i), location="Pasar Seni")
            for i in range(5)
        ]
    )
    client = TestClient(create_app())

    response = client.get("/api/trafficmy/gps-gaps", params={"limit": 2})
    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
