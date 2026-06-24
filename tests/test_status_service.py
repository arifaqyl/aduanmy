from app.db.session import reset_complaints, upsert_complaints
from app.schemas.complaint import ComplaintSchema
from app.services.status_service import get_trafficmy_status


def test_status_service_marks_recent_data_as_not_stale():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/1",
                author_handle="u1",
                created_at="2026-06-23T00:00:00Z",
                raw_text="MRT delay at Maluri",
                normalized_text="mrt delay at maluri",
                detected_language_mix="en",
                category="transport",
                entity="MRT",
                location="Maluri",
                severity="medium",
                confidence=0.8,
                cluster_id="transport:MRT:Maluri:delay",
            )
        ]
    )

    payload = get_trafficmy_status(stale_after_minutes=60 * 24 * 365)
    assert payload["product"] == "TrafficMY"
    assert payload["freshness"]["is_stale"] is False
    assert payload["totals"]["complaints"] == 1
