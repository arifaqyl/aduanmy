from app.services.ingest_service import transform_rows


def test_transform_rows_forces_official_grounding_to_low_severity():
    rows = transform_rows(
        {
            "official": [
                {
                    "source_platform": "official",
                    "post_id": "o1",
                    "url": "https://example.com/official",
                    "author_handle": "official",
                    "created_at": "",
                    "raw_text": "MyJPJ portal login error. Session expired and users cannot login during maintenance.",
                    "query": "official",
                    "seed_category": "gov_portals",
                }
            ]
        }
    )

    assert len(rows) == 1
    assert rows[0].severity == "low"


def test_transform_rows_rejects_generic_official_reference_pages():
    rows = transform_rows(
        {
            "official": [
                {
                    "source_platform": "official",
                    "post_id": "o-open-data",
                    "url": "https://example.com/open-data",
                    "author_handle": "official",
                    "created_at": "",
                    "raw_text": "Government open data portal for transport datasets and transparency access.",
                    "query": "official",
                    "seed_category": "transport",
                },
                {
                    "source_platform": "official",
                    "post_id": "o-weather-open",
                    "url": "https://example.com/weather-open",
                    "author_handle": "official",
                    "created_at": "",
                    "raw_text": "MET open data platform for public weather datasets and APIs.",
                    "query": "official",
                    "seed_category": "flood_weather",
                },
            ]
        }
    )

    assert rows == []


def test_transform_rows_rejects_route_less_official_transport_titles():
    rows = transform_rows(
        {
            "official": [
                {
                    "source_platform": "official",
                    "post_id": "o-bus-delay",
                    "url": "https://example.com/bus-delay",
                    "author_handle": "official:myrapid",
                    "created_at": "",
                    "raw_text": "Kelewatan Bas: 5 Laluan Terjejas",
                    "query": "official",
                    "seed_category": "transport",
                }
            ]
        }
    )

    assert rows == []


def test_transform_rows_keeps_specific_myrapid_line_update_titles_as_official_grounding():
    rows = transform_rows(
        {
            "official": [
                {
                    "source_platform": "official",
                    "post_id": "o-line",
                    "url": "https://example.com/line-update",
                    "author_handle": "official:myrapid",
                    "created_at": "",
                    "raw_text": "Kemas Kini Laluan Ampang/Sri Petaling",
                    "query": "Kemas Kini Laluan Ampang/Sri Petaling",
                    "seed_category": "transport",
                }
            ]
        }
    )

    assert len(rows) == 1
    assert rows[0].entity == "Ampang/Sri Petaling Line"
    assert rows[0].source_platform == "official"


def test_transform_rows_uses_transport_source_fallback_entity_for_rapidkl_handles():
    rows = transform_rows(
        {
            "x": [
                {
                    "source_platform": "x",
                    "post_id": "x1",
                    "url": "https://x.com/askrapidkl/status/1",
                    "author_handle": "askrapidkl",
                    "created_at": "",
                    "raw_text": "Maaf atas kelewatan. Next bas akan gerak jam 2040. Pada masa ini hanya sebuah bas beroperasi.",
                    "query": "seed_status",
                    "seed_category": "transport",
                }
            ]
        }
    )

    assert len(rows) == 1
    assert rows[0].entity == "RapidKL"
    assert rows[0].cluster_id == "transport:RapidKL:delay"


def test_transform_rows_rejects_transport_history_discussion_without_incident_language():
    rows = transform_rows(
        {
            "reddit": [
                {
                    "source_platform": "reddit",
                    "post_id": "r-history",
                    "url": "https://old.reddit.com/r/malaysia/comments/example",
                    "author_handle": "reddit:test",
                    "created_at": "",
                    "raw_text": "Bus routes in Kuala Lumpur and Selangor before 1998. I am compiling a list of operators and routes from memory.",
                    "query": "rapidkl delay",
                    "seed_category": "transport",
                }
            ]
        }
    )

    assert rows == []


def test_transform_rows_keeps_source_timestamps_from_threads_and_reddit():
    rows = transform_rows(
        {
            "threads": [
                {
                    "source_platform": "threads",
                    "post_id": "t-ts",
                    "url": "https://threads.example/post/1",
                    "author_handle": "threads:test",
                    "created_at": "2026-06-21T04:18:43.000Z",
                    "raw_text": "Tak boleh keluar stesen fire alarm kat MRT Maluri",
                    "query": "seed_url",
                    "seed_category": "transport",
                }
            ],
            "reddit": [
                {
                    "source_platform": "reddit",
                    "post_id": "r-ts",
                    "url": "https://old.reddit.com/r/malaysia/comments/abc",
                    "author_handle": "reddit:test",
                    "created_at": "2026-06-19T01:19:08+00:00",
                    "raw_text": "LRT3 Shah Alam Line has delays again this week",
                    "query": "kelana jaya line delay",
                    "seed_category": "transport",
                }
            ],
        }
    )

    assert len(rows) == 2
    assert rows[0].created_at or rows[1].created_at
    assert {row.created_at for row in rows} == {
        "2026-06-21T04:18:43.000Z",
        "2026-06-19T01:19:08+00:00",
    }
