from app.db.session import reset_complaints, upsert_complaints
from app.schemas.complaint import ComplaintSchema
from app.services.scoring_service import score_categories


def test_score_categories_prefers_transport_when_x_and_official_exist():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="x",
                post_id="x1",
                url="https://x.example/1",
                author_handle="askrapidkl",
                created_at="2026-06-22T00:00:00Z",
                raw_text="LRT incident",
                normalized_text="lrt incident kelana jaya line",
                detected_language_mix="en",
                category="transport",
                subcategory="",
                entity="LRT",
                location="Kelana Jaya",
                severity="high",
                confidence=0.8,
                engagement="",
                cluster_id="transport:LRT:Kelana Jaya:incident",
            ),
            ComplaintSchema(
                source_platform="official",
                post_id="o1",
                url="https://mot.example/1",
                author_handle="official",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Transport open data",
                normalized_text="transport open data",
                detected_language_mix="en",
                category="transport",
                subcategory="",
                entity="",
                location="",
                severity="low",
                confidence=0.2,
                engagement="",
                cluster_id="transport:official",
            ),
            ComplaintSchema(
                source_platform="reddit",
                post_id="r1",
                url="https://reddit.example/1",
                author_handle="u1",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Unifi down",
                normalized_text="unifi down",
                detected_language_mix="en",
                category="telco_internet",
                subcategory="",
                entity="Unifi",
                location="",
                severity="high",
                confidence=0.8,
                engagement="",
                cluster_id="telco_internet:Unifi:outage",
            ),
            ComplaintSchema(
                source_platform="official",
                post_id="o2",
                url="https://unifi.example/1",
                author_handle="official",
                created_at="2026-06-22T00:00:00Z",
                raw_text="Unifi support",
                normalized_text="unifi support",
                detected_language_mix="en",
                category="telco_internet",
                subcategory="",
                entity="Unifi",
                location="",
                severity="low",
                confidence=0.2,
                engagement="",
                cluster_id="telco_internet:Unifi",
            ),
        ]
    )

    scores = score_categories()
    assert scores[0]["category"] == "transport"
    assert scores[0]["realtime_provider_bonus"] == 2


def test_score_categories_excludes_official_from_density_and_diversity():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="official",
                post_id="o1",
                url="https://gov.example/1",
                author_handle="official",
                created_at="2026-06-22T00:00:00Z",
                raw_text="MyJPJ status page",
                normalized_text="myjpj status page",
                detected_language_mix="en",
                category="gov_portals",
                subcategory="",
                entity="MyJPJ",
                location="",
                severity="low",
                confidence=0.2,
                engagement="",
                cluster_id="gov_portals:MyJPJ",
            )
        ]
    )

    scores = score_categories()
    gov = scores[0]
    assert gov["category"] == "gov_portals"
    assert gov["source_density"] == 0
    assert gov["source_diversity"] == 0
    assert gov["verification_potential"] == 2
