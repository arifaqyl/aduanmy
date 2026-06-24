from app.db.session import reset_complaints, upsert_complaints
from app.schemas.complaint import ComplaintSchema
from app.services.incident_service import get_cluster_detail, list_clusters


def test_list_clusters_uses_highest_severity_rank_not_lexical_max():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/1",
                author_handle="u1",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Unifi slow today",
                normalized_text="unifi slow today",
                detected_language_mix="en",
                category="telco_internet",
                entity="Unifi",
                location="",
                severity="medium",
                confidence=0.6,
                cluster_id="telco_internet:Unifi:outage",
            ),
            ComplaintSchema(
                source_platform="reddit",
                post_id="r1",
                url="https://example.com/2",
                author_handle="u2",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Unifi down",
                normalized_text="unifi down",
                detected_language_mix="en",
                category="telco_internet",
                entity="Unifi",
                location="",
                severity="high",
                confidence=0.9,
                cluster_id="telco_internet:Unifi:outage",
            ),
        ]
    )

    cluster = list_clusters()[0]
    assert cluster["cluster_id"] == "telco_internet:Unifi:outage"
    assert cluster["severity"] == "high"
    assert cluster["volume"] == 2
    assert cluster["confidence_band"] in {"strong", "reasonable"}


def test_list_clusters_excludes_official_grounding_by_default():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="official",
                post_id="o1",
                url="https://example.com/official",
                author_handle="official",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Transport status page",
                normalized_text="transport status page",
                detected_language_mix="en",
                category="transport",
                entity="",
                location="",
                severity="low",
                confidence=0.2,
                cluster_id="transport:official",
            ),
            ComplaintSchema(
                source_platform="x",
                post_id="x1",
                url="https://example.com/x1",
                author_handle="askrapidkl",
                created_at="2026-06-22T00:00:00Z",
                raw_text="LRT incident",
                normalized_text="lrt incident kelana jaya line",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Kelana Jaya",
                severity="high",
                confidence=0.9,
                cluster_id="transport:LRT:Kelana Jaya:incident",
            ),
        ]
    )

    clusters = list_clusters()
    assert len(clusters) == 1
    assert clusters[0]["cluster_id"] == "transport:LRT:Kelana Jaya:incident"
    assert clusters[0]["corroborated_by_official"] is False


def test_list_clusters_can_include_official_grounding_when_requested():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="official",
                post_id="o1",
                url="https://example.com/official",
                author_handle="official",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Transport status page",
                normalized_text="transport status page",
                detected_language_mix="en",
                category="transport",
                entity="",
                location="",
                severity="low",
                confidence=0.2,
                cluster_id="transport:official",
            ),
            ComplaintSchema(
                source_platform="x",
                post_id="x1",
                url="https://example.com/x1",
                author_handle="askrapidkl",
                created_at="2026-06-22T00:00:00Z",
                raw_text="LRT incident",
                normalized_text="lrt incident kelana jaya line",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Kelana Jaya",
                severity="high",
                confidence=0.9,
                cluster_id="transport:LRT:Kelana Jaya:incident",
            ),
        ]
    )

    clusters = list_clusters(include_official=True)
    ids = {cluster["cluster_id"] for cluster in clusters}
    assert "transport:official" in ids
    assert "transport:LRT:Kelana Jaya:incident" in ids


def test_list_clusters_adds_confidence_score_inputs():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/1",
                author_handle="u1",
                created_at="2026-06-22T00:00:00Z",
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
                source_platform="official",
                post_id="o1",
                url="https://example.com/official",
                author_handle="official",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Transport status page",
                normalized_text="transport status page",
                detected_language_mix="en",
                category="transport",
                entity="",
                location="",
                severity="low",
                confidence=0.2,
                cluster_id="transport:official",
            ),
        ]
    )

    cluster = list_clusters()[0]
    assert cluster["confidence_score"] > 0
    assert cluster["confidence_band"] in {"weak", "reasonable", "strong"}
    assert cluster["source_count"] == 1


def test_list_clusters_requires_specific_official_match_for_corroboration():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="reddit",
                post_id="r1",
                url="https://example.com/reddit",
                author_handle="u1",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Unifi down",
                normalized_text="unifi down",
                detected_language_mix="en",
                category="telco_internet",
                entity="Unifi",
                location="",
                severity="high",
                confidence=0.8,
                cluster_id="telco_internet:Unifi:outage",
            ),
            ComplaintSchema(
                source_platform="official",
                post_id="o1",
                url="https://example.com/official",
                author_handle="official",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Unifi status page",
                normalized_text="unifi status page",
                detected_language_mix="en",
                category="telco_internet",
                entity="Unifi",
                location="",
                severity="low",
                confidence=0.2,
                cluster_id="telco_internet:official",
            ),
        ]
    )

    cluster = list_clusters()[0]
    assert cluster["corroborated_by_official"] is True


def test_list_clusters_allows_line_level_official_corroboration_for_station_level_transport_incident():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/threads",
                author_handle="u1",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Ampang/Sri Petaling line disruption near Chan Sow Lin",
                normalized_text="ampang/sri petaling line disruption near chan sow lin",
                detected_language_mix="en",
                category="transport",
                entity="Ampang/Sri Petaling Line",
                location="Chan Sow Lin",
                severity="high",
                confidence=0.8,
                cluster_id="transport:Ampang/Sri Petaling Line:Chan Sow Lin:disruption",
            ),
            ComplaintSchema(
                source_platform="official",
                post_id="o1",
                url="https://example.com/official",
                author_handle="official:myrapid",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Kemas Kini Laluan Ampang/Sri Petaling",
                normalized_text="kemas kini laluan ampang/sri petaling",
                detected_language_mix="ms",
                category="transport",
                entity="Ampang/Sri Petaling Line",
                location="",
                severity="low",
                confidence=0.2,
                cluster_id="transport:official",
            ),
        ]
    )

    cluster = list_clusters()[0]
    assert cluster["corroborated_by_official"] is True


def test_list_clusters_can_filter_by_confidence_band():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/1",
                author_handle="u1",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Unifi down",
                normalized_text="unifi down",
                detected_language_mix="en",
                category="telco_internet",
                entity="Unifi",
                location="",
                severity="high",
                confidence=0.9,
                cluster_id="telco_internet:Unifi:outage",
            ),
            ComplaintSchema(
                source_platform="reddit",
                post_id="r1",
                url="https://example.com/2",
                author_handle="u2",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Unifi down too",
                normalized_text="unifi down too",
                detected_language_mix="en",
                category="telco_internet",
                entity="Unifi",
                location="",
                severity="high",
                confidence=0.9,
                cluster_id="telco_internet:Unifi:outage",
            ),
            ComplaintSchema(
                source_platform="official",
                post_id="o1",
                url="https://example.com/official",
                author_handle="official",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Unifi official status",
                normalized_text="unifi official status",
                detected_language_mix="en",
                category="telco_internet",
                entity="Unifi",
                location="",
                severity="low",
                confidence=0.2,
                cluster_id="telco_internet:official",
            ),
        ]
    )

    strong = list_clusters(confidence_band="strong")
    assert len(strong) == 1
    assert strong[0]["cluster_id"] == "telco_internet:Unifi:outage"


def test_list_clusters_exposes_source_roles_for_public_media_and_official():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/threads",
                author_handle="thesundaily",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Kelana Jaya Line incident",
                normalized_text="kelana jaya line incident",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Dang Wangi",
                severity="high",
                confidence=0.9,
                cluster_id="transport:Kelana Jaya Line:Dang Wangi:incident",
            ),
            ComplaintSchema(
                source_platform="x",
                post_id="x1",
                url="https://example.com/x",
                author_handle="askrapidkl",
                created_at="2026-06-22T00:05:00Z",
                raw_text="Kelana Jaya Line incident",
                normalized_text="kelana jaya line incident",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Dang Wangi",
                severity="high",
                confidence=0.9,
                cluster_id="transport:Kelana Jaya Line:Dang Wangi:incident",
            ),
            ComplaintSchema(
                source_platform="official",
                post_id="o1",
                url="https://example.com/official",
                author_handle="official:myrapid",
                created_at="",
                raw_text="Kemas Kini Laluan Kelana Jaya",
                normalized_text="kemas kini laluan kelana jaya",
                detected_language_mix="ms",
                category="transport",
                entity="Kelana Jaya Line",
                location="",
                severity="low",
                confidence=0.2,
                cluster_id="transport:official",
            ),
        ]
    )

    cluster = list_clusters()[0]
    assert cluster["cluster_id"] == "transport:Kelana Jaya Line:Dang Wangi:incident"
    assert cluster["source_roles"] == ["public_signal", "media_report", "official_grounding"]


def test_list_clusters_marks_threads_media_only_cluster_as_media_report_not_public_signal():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/threads",
                author_handle="thesundaily",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Kelana Jaya Line incident",
                normalized_text="kelana jaya line incident",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Dang Wangi",
                severity="high",
                confidence=0.9,
                cluster_id="transport:Kelana Jaya Line:Dang Wangi:incident",
            ),
        ]
    )

    cluster = list_clusters()[0]
    assert cluster["source_roles"] == ["media_report"]


def test_get_cluster_detail_returns_items_and_breakdown():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="x",
                post_id="x1",
                url="https://example.com/x1",
                author_handle="askrapidkl",
                created_at="2026-06-22T00:00:00Z",
                raw_text="LRT incident",
                normalized_text="lrt incident kelana jaya line",
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
                created_at="2026-06-22T00:00:00Z",
                raw_text="LRT incident too",
                normalized_text="lrt incident kelana jaya line",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Kelana Jaya",
                severity="high",
                confidence=0.8,
                cluster_id="transport:LRT:Kelana Jaya:incident",
            ),
        ]
    )

    detail = get_cluster_detail("transport:LRT:Kelana Jaya:incident")
    assert detail is not None
    assert detail["cluster"]["cluster_id"] == "transport:LRT:Kelana Jaya:incident"
    assert detail["source_breakdown"]["x"] == 1
    assert detail["source_breakdown"]["threads"] == 1
    assert len(detail["items"]) == 2


def test_cluster_timestamps_prefer_source_created_at_over_inserted_at():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="x",
                post_id="x-old",
                url="https://example.com/x-old",
                author_handle="myrapidkl",
                created_at="2022-11-08T10:00:00Z",
                raw_text="LRT disruption old notice",
                normalized_text="lrt disruption old notice",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Kuala Lumpur",
                severity="low",
                confidence=0.4,
                cluster_id="transport:LRT:Kuala Lumpur:disruption",
            )
        ]
    )

    cluster = list_clusters(category="transport")[0]
    detail = get_cluster_detail("transport:LRT:Kuala Lumpur:disruption")

    assert cluster["last_seen_at"].startswith("2022-11-08")
    assert detail is not None
    assert detail["cluster"]["first_seen_at"].startswith("2022-11-08")
    assert detail["cluster"]["last_seen_at"].startswith("2022-11-08")


def test_clusters_expose_freshness_bucket_and_age_days():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="recent-1",
                url="https://example.com/recent-1",
                author_handle="u1",
                created_at="2026-06-22T00:00:00Z",
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
                post_id="aging-1",
                url="https://example.com/aging-1",
                author_handle="askrapidkl",
                created_at="2026-06-12T00:00:00Z",
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
            ComplaintSchema(
                source_platform="reddit",
                post_id="stale-1",
                url="https://example.com/stale-1",
                author_handle="u2",
                created_at="2026-05-12T00:00:00Z",
                raw_text="LRT disruption at Chan Sow Lin",
                normalized_text="lrt disruption at chan sow lin",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Chan Sow Lin",
                severity="medium",
                confidence=0.6,
                cluster_id="transport:LRT:Chan Sow Lin:disruption",
            ),
        ]
    )

    clusters = {cluster["cluster_id"]: cluster for cluster in list_clusters(category="transport")}

    assert clusters["transport:MRT:Maluri:incident"]["freshness_bucket"] == "recent"
    assert clusters["transport:Kelana Jaya Line:Bangsar:delay"]["freshness_bucket"] == "aging"
    assert clusters["transport:LRT:Chan Sow Lin:disruption"]["freshness_bucket"] == "stale"
    assert clusters["transport:MRT:Maluri:incident"]["age_days"] is not None
