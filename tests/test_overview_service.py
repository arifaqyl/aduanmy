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
                raw_text="LRT incident at Kelana Jaya — stuck again",
                normalized_text="lrt incident at kelana jaya stuck again",
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
                raw_text="MRT delay at Maluri this morning",
                normalized_text="mrt delay at maluri this morning",
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

    default_payload = get_trafficmy_incidents(sort_by="freshest", freshness_band="all")
    full_payload = get_trafficmy_incidents(sort_by="freshest", include_stale=True, freshness_band="all")

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
                raw_text="Kelana Jaya line incident near Dang Wangi today",
                normalized_text="kelana jaya line incident near dang wangi today",
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
                raw_text="Kelana Jaya Line incident at Pasar Seni this morning",
                normalized_text="kelana jaya line incident at pasar seni this morning",
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
                raw_text="Kelana Jaya Line incident at Dang Wangi today",
                normalized_text="kelana jaya line incident at dang wangi today",
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


def test_overview_top_incidents_prefers_reasonable_or_strong_over_weak_when_available():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="reasonable-1",
                url="https://example.com/reasonable-1",
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
                post_id="weak-1",
                url="https://example.com/weak-1",
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

    payload = get_trafficmy_overview(include_stale=True)
    top_ids = [item["cluster_id"] for item in payload["top_incidents"]]

    assert "transport:MRT:Maluri:incident" in top_ids
    assert "transport:Kelana Jaya Line:Bangsar:delay" not in top_ids


def test_default_source_group_hides_gtfs_only_clusters():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="gtfs_rt",
                post_id="g1",
                url="https://example.com/g1",
                author_handle="gtfs:rapid-bus-kl",
                created_at="2026-06-28T06:48:31Z",
                raw_text="GTFS anomaly route 772",
                normalized_text="gtfs anomaly route 772",
                detected_language_mix="en",
                category="transport",
                entity="772",
                location="Pasar Seni",
                severity="medium",
                confidence=0.8,
                cluster_id="transport:772:Pasar Seni",
            ),
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/t1",
                author_handle="k.sam95",
                created_at="2026-06-25T00:48:11Z",
                raw_text="Kelana Jaya LRT line delay again this morning stuck at Bangsar",
                normalized_text="kelana jaya lrt line delay again this morning stuck at bangsar",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Kelana Jaya",
                severity="high",
                confidence=0.8,
                cluster_id="transport:Kelana Jaya Line:Kelana Jaya:delay",
            ),
        ]
    )

    social = get_trafficmy_incidents(source_group="social", freshness_band="all")
    gps = get_trafficmy_incidents(source_group="gps", freshness_band="all")

    assert social["count"] == 1
    assert social["items"][0]["sources"] == "threads"
    assert gps["count"] == 1
    assert gps["items"][0]["sources"] == "gtfs_rt"


def test_quality_only_hides_reply_thread_noise():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="noise",
                url="https://example.com/noise",
                author_handle="lelzilla45",
                created_at="2026-06-16T00:51:16Z",
                raw_text="lelzilla45 Replying to @x LRT Chan Sow Lin nice station",
                normalized_text="lelzilla45 replying to @x lrt chan sow lin nice station",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Chan Sow Lin",
                severity="low",
                confidence=0.5,
                cluster_id="transport:LRT:Chan Sow Lin:delay",
            ),
            ComplaintSchema(
                source_platform="threads",
                post_id="real",
                url="https://example.com/real",
                author_handle="k.sam95",
                created_at="2026-06-25T00:48:11Z",
                raw_text="Kelana Jaya LRT line delay again this morning stuck at Bangsar",
                normalized_text="kelana jaya lrt line delay again this morning stuck at bangsar",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Bangsar",
                severity="medium",
                confidence=0.8,
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            ),
        ]
    )

    payload = get_trafficmy_incidents(quality_only=True, freshness_band="all")
    ids = {item["cluster_id"] for item in payload["items"]}
    assert "transport:Kelana Jaya Line:Bangsar:delay" in ids
    assert "transport:LRT:Chan Sow Lin:delay" not in ids


def test_quality_only_hides_hypothetical_pasar_seni_post():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="hypo",
                url="https://example.com/hypo",
                author_handle="yyadnn",
                created_at="2026-06-23T23:53:13Z",
                raw_text=(
                    "Bayangkan LRT3 dah start operate lepastu KJ line ada problem/delay, "
                    "station Glenmarie akan jd macam Pasar Seni?"
                ),
                normalized_text=(
                    "bayangkan lrt3 dah start operate lepastu kj line ada problem/delay "
                    "station glenmarie akan jd macam pasar seni"
                ),
                detected_language_mix="en",
                category="transport",
                entity="",
                location="Pasar Seni",
                severity="medium",
                confidence=0.5,
                cluster_id="transport:Pasar Seni:delay",
            ),
            ComplaintSchema(
                source_platform="reddit",
                post_id="advisory",
                url="https://example.com/advisory",
                author_handle="news",
                created_at="2026-06-24T03:35:05Z",
                raw_text="Commuters on the Kelana Jaya Line can expect delays.",
                normalized_text="commuters on the kelana jaya line can expect delays.",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="",
                severity="medium",
                confidence=0.5,
                cluster_id="transport:Kelana Jaya Line:delay",
            ),
        ]
    )

    payload = get_trafficmy_incidents(quality_only=True, freshness_band="all")
    ids = {item["cluster_id"] for item in payload["items"]}
    assert "transport:Pasar Seni:delay" not in ids
    assert "transport:Kelana Jaya Line:delay" not in ids
