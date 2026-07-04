from app.services.public_incident_service import detect_facility_alert, public_cluster, public_evidence, public_incident_copy


def test_public_copy_glance_line_includes_when_line_place_issue():
    cluster = {
        "cluster_id": "transport:Kelana Jaya Line:Bangsar:delay",
        "entity": "Kelana Jaya Line",
        "location": "Bangsar",
        "severity": "medium",
        "volume": 1,
        "source_count": 1,
        "last_seen_at": "2026-07-03T10:30:00Z",
        "example_text": "hari ni stuck at Bangsar waiting 25 minutes for train",
    }
    copy = public_incident_copy(cluster)
    public = public_cluster(cluster)

    assert "Kelana Jaya Line" in copy["glance_line"]
    assert "Bangsar" in copy["glance_line"]
    assert "25 min" in copy["glance_line"] or "delay" in copy["glance_line"].lower()
    assert copy["headline"].startswith("Kelana Jaya Line")
    assert "stuck at Bangsar" in copy["summary"] or "25 minutes" in copy["summary"]
    assert "example_text" not in public
    assert "author_handles" not in public


def test_public_copy_strips_threads_handle_prefix():
    cluster = {
        "cluster_id": "transport:Kelana Jaya Line::delay",
        "entity": "Kelana Jaya Line",
        "location": "",
        "severity": "medium",
        "volume": 1,
        "source_count": 1,
        "last_seen_at": "2026-07-03T08:00:00Z",
        "example_text": "rider123 2h Kelana Jaya Line delay again, train tak gerak",
    }
    copy = public_incident_copy(cluster)
    assert "rider123 2h" not in copy["summary"]
    assert "tak gerak" in copy["summary"]


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
