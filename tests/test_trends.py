from app.db.session import reset_complaints, upsert_complaints
from app.schemas.complaint import ComplaintSchema
from app.services.trends_service import get_trends


def test_trends_summary_has_expected_counts():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="1",
                url="https://example.com/1",
                author_handle="u1",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Unifi down in Kuala Lumpur",
                normalized_text="unifi down in kuala lumpur",
                detected_language_mix="en",
                category="telco_internet",
                entity="Unifi",
                location="Kuala Lumpur",
                severity="high",
                confidence=0.8,
                cluster_id="telco_internet:Unifi",
            ),
            ComplaintSchema(
                source_platform="reddit",
                post_id="2",
                url="https://example.com/2",
                author_handle="u2",
                created_at="2026-06-22T01:00:00Z",
                raw_text="MRT delay at KL Sentral",
                normalized_text="mrt delay at kl sentral",
                detected_language_mix="en",
                category="transport",
                entity="MRT",
                location="KL Sentral",
                severity="medium",
                confidence=0.7,
                cluster_id="transport:MRT",
            ),
        ]
    )

    trends = get_trends(limit_terms=5)
    assert trends["totals"]["complaints"] == 2
    assert trends["top_categories"][0]["name"] in {"telco_internet", "transport"}
    assert any(item["name"] == "Unifi" for item in trends["top_entities"])
    assert any(item["name"] == "Kuala Lumpur" for item in trends["top_locations"])
    assert len(trends["freshest"]) == 2


def test_trends_term_mining_excludes_unhelpful_telco_tv_terms():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="reddit",
                post_id="3",
                url="https://example.com/3",
                author_handle="u3",
                created_at="2026-06-22T02:00:00Z",
                raw_text="Astro HBO channels may leave Unifi TV",
                normalized_text="astro hbo channels may leave unifi tv",
                detected_language_mix="en",
                category="telco_internet",
                entity="Unifi",
                location="",
                severity="low",
                confidence=0.2,
                cluster_id="telco_internet:Unifi",
            )
        ]
    )

    trends = get_trends(limit_terms=10)
    terms = {item["term"] for item in trends["top_terms"]}
    assert "astro" not in terms
    assert "hbo" not in terms


def test_trends_term_mining_excludes_generic_admin_terms():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="reddit",
                post_id="4",
                url="https://example.com/4",
                author_handle="u4",
                created_at="2026-06-22T03:00:00Z",
                raw_text="Grab app account photo renew roadtax problem with MyJPJ",
                normalized_text="grab app account photo renew roadtax problem with myjpj",
                detected_language_mix="en",
                category="gov_portals",
                entity="MyJPJ",
                location="",
                severity="medium",
                confidence=0.5,
                cluster_id="gov_portals:MyJPJ",
            )
        ]
    )

    trends = get_trends(limit_terms=10)
    terms = {item["term"] for item in trends["top_terms"]}
    assert "grab" not in terms
    assert "account" not in terms
    assert "photo" not in terms


def test_trends_term_mining_excludes_entity_and_location_tokens():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="5",
                url="https://example.com/5",
                author_handle="u5",
                created_at="2026-06-22T04:00:00Z",
                raw_text="LRT Kelana Jaya line experiencing incident and major delay",
                normalized_text="lrt kelana jaya line experiencing incident and major delay",
                detected_language_mix="en",
                category="transport",
                entity="LRT",
                location="Kelana Jaya",
                severity="high",
                confidence=0.8,
                cluster_id="transport:LRT:Kelana Jaya",
            )
        ]
    )

    trends = get_trends(limit_terms=10)
    terms = {item["term"] for item in trends["top_terms"]}
    assert "lrt" not in terms
    assert "kelana" not in terms
    assert "jaya" not in terms
    assert "incident" in terms or "major" in terms or "experiencing" in terms


def test_trends_exclude_official_rows_from_complaint_rankings():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="official",
                post_id="o1",
                url="https://official.example/1",
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
                source_platform="threads",
                post_id="t1",
                url="https://threads.example/1",
                author_handle="u1",
                created_at="2026-06-22T00:10:00Z",
                raw_text="Unifi down in Kuala Lumpur",
                normalized_text="unifi down in kuala lumpur",
                detected_language_mix="en",
                category="telco_internet",
                entity="Unifi",
                location="Kuala Lumpur",
                severity="high",
                confidence=0.8,
                cluster_id="telco_internet:Unifi:outage",
            ),
        ]
    )

    trends = get_trends(limit_terms=5)
    assert trends["totals"]["complaints"] == 1
    assert trends["totals"]["grounding_rows"] == 1
    assert trends["top_categories"] == [{"name": "telco_internet", "count": 1}]


def test_trends_term_mining_excludes_handles_and_reply_filler():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="x",
                post_id="x1",
                url="https://x.example/1",
                author_handle="askrapidkl",
                created_at="2026-06-22T00:00:00Z",
                raw_text="@shawtyrapunzel Hi bij maaf atas kelewatan next bas akan gerak jam 2040",
                normalized_text="@shawtyrapunzel hi bij maaf atas kelewatan next bas akan gerak jam 2040",
                detected_language_mix="rojak",
                category="transport",
                entity="",
                location="",
                severity="medium",
                confidence=0.7,
                cluster_id="transport:delay",
            )
        ]
    )

    trends = get_trends(limit_terms=10)
    terms = {item["term"] for item in trends["top_terms"]}
    assert "shawtyrapunzel" not in terms
    assert "hi" not in terms
    assert "bij" not in terms
