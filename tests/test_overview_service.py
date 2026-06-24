from datetime import UTC, datetime, timedelta

from app.db.session import reset_complaints, upsert_complaints
from app.schemas.complaint import ComplaintSchema
from app.services.overview_service import get_trafficmy_incidents, get_trafficmy_overview


def test_overview_derives_live_entity_and_location_counts_from_clusters():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="x",
                post_id="x1",
                url="https://example.com/x1",
                author_handle="askrapidkl",
                created_at="2026-06-22T00:00:00Z",
                raw_text="LRT incident at Kelana Jaya",
                normalized_text="lrt incident at kelana jaya",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Kelana Jaya",
                severity="high",
                confidence=0.9,
                cluster_id="transport:LRT:Kelana Jaya:incident",
            ),
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/t1",
                author_handle="u1",
                created_at="2026-06-22T00:10:00Z",
                raw_text="LRT incident at Kelana Jaya again",
                normalized_text="lrt incident at kelana jaya again",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Kelana Jaya",
                severity="high",
                confidence=0.8,
                cluster_id="transport:LRT:Kelana Jaya:incident",
            ),
            ComplaintSchema(
                source_platform="reddit",
                post_id="r1",
                url="https://example.com/r1",
                author_handle="u2",
                created_at="2026-06-22T00:20:00Z",
                raw_text="MRT issue at Maluri",
                normalized_text="mrt issue at maluri",
                detected_language_mix="en",
                category="transport",
                entity="MRT",
                location="Maluri",
                severity="medium",
                confidence=0.7,
                cluster_id="transport:MRT:Maluri:incident",
            ),
        ]
    )

    payload = get_trafficmy_overview()
    assert payload["product"] == "TrafficMY"

    entities = {item["name"]: item["count"] for item in payload["transport_entities"]}
    locations = {item["name"]: item["count"] for item in payload["transport_locations"]}

    assert entities["LRT"] == 2
    assert entities["MRT"] == 1
    assert locations["Kelana Jaya"] == 2
    assert locations["Maluri"] == 1


def test_overview_hides_stale_transport_clusters_by_default():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="recent",
                url="https://example.com/recent",
                author_handle="u1",
                created_at="2026-06-21T04:18:43Z",
                raw_text="MRT fire alarm at Maluri",
                normalized_text="mrt fire alarm at maluri",
                detected_language_mix="en",
                category="transport",
                entity="MRT",
                location="Maluri",
                severity="high",
                confidence=0.8,
                cluster_id="transport:MRT:Maluri:incident",
            ),
            ComplaintSchema(
                source_platform="x",
                post_id="stale",
                url="https://example.com/stale",
                author_handle="askrapidkl",
                created_at="2026-05-12T11:50:51Z",
                raw_text="Kelana Jaya Line delay",
                normalized_text="kelana jaya line delay",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Bangsar",
                severity="medium",
                confidence=0.6,
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            ),
        ]
    )

    payload = get_trafficmy_overview()
    assert payload["summary"]["transport_cluster_count"] == 1
    assert payload["summary"]["stale_hidden_count"] == 1
    assert payload["top_incidents"][0]["cluster_id"] == "transport:MRT:Maluri:incident"


def test_incidents_can_include_stale_when_requested():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="recent",
                url="https://example.com/recent",
                author_handle="u1",
                created_at="2026-06-21T04:18:43Z",
                raw_text="MRT fire alarm at Maluri",
                normalized_text="mrt fire alarm at maluri",
                detected_language_mix="en",
                category="transport",
                entity="MRT",
                location="Maluri",
                severity="high",
                confidence=0.8,
                cluster_id="transport:MRT:Maluri:incident",
            ),
            ComplaintSchema(
                source_platform="x",
                post_id="stale",
                url="https://example.com/stale",
                author_handle="askrapidkl",
                created_at="2026-05-12T11:50:51Z",
                raw_text="Kelana Jaya Line delay",
                normalized_text="kelana jaya line delay",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Bangsar",
                severity="medium",
                confidence=0.6,
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            ),
        ]
    )

    default_payload = get_trafficmy_incidents(sort_by="freshest")
    full_payload = get_trafficmy_incidents(sort_by="freshest", include_stale=True)

    assert default_payload["count"] == 1
    assert default_payload["stale_hidden_count"] == 1
    assert full_payload["count"] == 2
    assert full_payload["filters"]["include_stale"] is True


def test_overview_can_include_stale_when_requested():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="recent",
                url="https://example.com/recent",
                author_handle="u1",
                created_at="2026-06-21T04:18:43Z",
                raw_text="MRT fire alarm at Maluri",
                normalized_text="mrt fire alarm at maluri",
                detected_language_mix="en",
                category="transport",
                entity="MRT",
                location="Maluri",
                severity="high",
                confidence=0.8,
                cluster_id="transport:MRT:Maluri:incident",
            ),
            ComplaintSchema(
                source_platform="x",
                post_id="stale",
                url="https://example.com/stale",
                author_handle="askrapidkl",
                created_at="2026-05-12T11:50:51Z",
                raw_text="Kelana Jaya Line delay",
                normalized_text="kelana jaya line delay",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Bangsar",
                severity="medium",
                confidence=0.6,
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            ),
        ]
    )

    default_payload = get_trafficmy_overview()
    full_payload = get_trafficmy_overview(include_stale=True)

    assert default_payload["summary"]["transport_cluster_count"] == 1
    assert default_payload["summary"]["include_stale"] is False
    assert full_payload["summary"]["transport_cluster_count"] == 2
    assert full_payload["summary"]["include_stale"] is True


def test_default_live_surface_keeps_aging_transport_incidents_inside_window():
    reset_complaints()
    aging = (datetime.now(UTC) - timedelta(days=18)).isoformat().replace("+00:00", "Z")
    stale = (datetime.now(UTC) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="aging",
                url="https://example.com/aging",
                author_handle="u1",
                created_at=aging,
                raw_text="Kelana Jaya line incident near Dang Wangi",
                normalized_text="kelana jaya line incident near dang wangi",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Dang Wangi",
                severity="high",
                confidence=0.8,
                cluster_id="transport:Kelana Jaya Line:Dang Wangi:incident",
            ),
            ComplaintSchema(
                source_platform="x",
                post_id="stale",
                url="https://example.com/stale",
                author_handle="askrapidkl",
                created_at=stale,
                raw_text="Chan Sow Lin delay",
                normalized_text="chan sow lin delay",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Chan Sow Lin",
                severity="medium",
                confidence=0.6,
                cluster_id="transport:LRT:Chan Sow Lin:delay",
            ),
        ]
    )

    payload = get_trafficmy_overview()
    assert payload["summary"]["transport_cluster_count"] == 1
    assert payload["summary"]["stale_hidden_count"] == 1
    assert payload["top_incidents"][0]["freshness_bucket"] == "aging"


def test_strongest_transport_sort_prefers_recent_over_older_when_confidence_band_matches():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="reddit",
                post_id="recent-1",
                url="https://example.com/recent-1",
                author_handle="u1",
                created_at="2026-06-24T00:00:00Z",
                raw_text="Kelana Jaya Line incident at Pasar Seni",
                normalized_text="kelana jaya line incident at pasar seni",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Pasar Seni",
                severity="high",
                confidence=0.8,
                cluster_id="transport:Kelana Jaya Line:Pasar Seni:incident",
            ),
            ComplaintSchema(
                source_platform="threads",
                post_id="aging-1",
                url="https://example.com/aging-1",
                author_handle="thesundaily",
                created_at="2026-06-05T00:00:00Z",
                raw_text="Kelana Jaya Line incident at Dang Wangi",
                normalized_text="kelana jaya line incident at dang wangi",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Dang Wangi",
                severity="high",
                confidence=0.8,
                cluster_id="transport:Kelana Jaya Line:Dang Wangi:incident",
            ),
        ]
    )

    payload = get_trafficmy_overview()
    assert payload["top_incidents"][0]["cluster_id"] == "transport:Kelana Jaya Line:Pasar Seni:incident"
