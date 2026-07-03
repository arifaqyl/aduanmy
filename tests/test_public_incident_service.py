from app.services.public_incident_service import detect_facility_alert, public_cluster, public_evidence, public_incident_copy


def test_public_copy_synthesizes_without_rider_quote():
    cluster = {
        "cluster_id": "transport:Kelana Jaya Line:Bangsar:delay",
        "entity": "Kelana Jaya Line",
        "location": "Bangsar",
        "severity": "medium",
        "volume": 2,
        "source_count": 1,
        "example_text": "rider slang and unverified nonsense",
        "author_handles": "someone",
    }
    copy = public_incident_copy(cluster)
    public = public_cluster(cluster)

    assert copy["headline"] == "Possible delays on Kelana Jaya Line"
    assert copy["headline_ms"] == "Kelewatan mungkin di Kelana Jaya Line"
    assert "Multiple recent rider signals" in copy["summary"]
    assert "isyarat penumpang" in copy["summary_ms"].lower()
    assert "example_text" not in public
    assert "author_handles" not in public
    assert "nonsense" not in str(public)


def test_detect_facility_alert_from_lift_keyword():
    cluster = {"entity": "KTM Komuter", "location": "KL Sentral", "example_text": "lift rosak lagi"}
    assert detect_facility_alert(cluster) == "facility"


def test_public_evidence_exposes_source_link_not_raw_post():
    evidence = public_evidence(
        {
            "source_platform": "threads",
            "created_at": "2026-06-30T10:00:00Z",
            "url": "https://threads.com/post/1",
            "raw_text": "unfiltered rider quote",
            "author_handle": "rider",
            "entity": "MRT Kajang Line",
        }
    )
    assert evidence["url"].endswith("/1")
    assert "raw_text" not in evidence
    assert "author_handle" not in evidence
