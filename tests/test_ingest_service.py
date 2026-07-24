from datetime import timedelta

from app.core.freshness import myt_day_start
from app.db.session import connect, init_db, upsert_complaints
from app.schemas.complaint import ComplaintSchema
from app.services.ingest_service import _collector_due, prune_rejected_threads_complaints, transform_rows


def _today_iso(hours: int = 9) -> str:
    """A timestamp guaranteed to fall on today's MYT calendar date — transform_rows
    only accepts social-platform transport rows from today, so fixtures must be dynamic."""
    return (myt_day_start() + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def test_gtfs_anomaly_collection_is_disabled_by_default():
    due, reason = _collector_due("gtfs", respect_cadence=False)
    assert due is False
    assert reason == "reference_only"


def test_reddit_forced_when_threads_empty(monkeypatch):
    monkeypatch.setattr(
        "app.services.ingest_service.latest_collector_run",
        lambda name, include_paused=False: (
            {"status": "empty", "finished_at": "2026-07-22T09:00:00Z"}
            if name == "threads"
            else {"status": "empty", "finished_at": "2026-07-22T09:00:00Z"}
        ),
    )
    monkeypatch.setattr("app.services.ingest_service.settings.reddit_min_interval_seconds", 7200)
    monkeypatch.setattr("app.services.ingest_service.is_myt_peak_hour", lambda: False)
    due, reason = _collector_due("reddit", respect_cadence=True)
    assert due is True
    assert reason == ""


def test_reddit_respects_cadence_when_threads_healthy(monkeypatch):
    from datetime import UTC, datetime

    now = datetime.now(UTC)

    def fake_latest(name, include_paused=False):
        if name == "threads":
            return {"status": "healthy", "finished_at": now.isoformat().replace("+00:00", "Z")}
        return {"status": "empty", "finished_at": now.isoformat().replace("+00:00", "Z")}

    monkeypatch.setattr("app.services.ingest_service.latest_collector_run", fake_latest)
    monkeypatch.setattr("app.services.ingest_service.settings.reddit_min_interval_seconds", 7200)
    monkeypatch.setattr("app.services.ingest_service.is_myt_peak_hour", lambda: False)
    due, reason = _collector_due("reddit", respect_cadence=True)
    assert due is False
    assert reason.startswith("cadence:")


def test_transform_rows_rejects_future_opening_sabotage_as_live_disruption():
    rows = transform_rows(
        {
            "threads": [
                {
                    "source_platform": "threads",
                    "post_id": "future-lrt3",
                    "url": "https://threads.example/future-lrt3",
                    "author_handle": "test",
                    "created_at": "2026-06-15T16:29:06Z",
                    "raw_text": "I am going to steal LRT Shah Alam cable just to delay their opening again wish me luck",
                    "query": "lrt delay",
                    "seed_category": "transport",
                }
            ]
        }
    )
    assert rows == []


def test_prune_rejected_threads_complaints_removes_legacy_noise():
    init_db()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="valid",
                url="https://threads.example/valid",
                author_handle="rider",
                created_at="2026-07-01T00:00:00Z",
                raw_text="LRT Kelana Jaya delay again, waiting 25 minutes at Bangsar",
                normalized_text="lrt kelana jaya delay again, waiting 25 minutes at bangsar",
                detected_language_mix="en",
                category="transport",
                subcategory="rail",
                entity="Kelana Jaya Line",
                location="Bangsar",
                state="Wilayah Persekutuan",
                severity="medium",
                confidence=0.5,
                engagement="",
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            ),
            ComplaintSchema(
                source_platform="threads",
                post_id="football",
                url="https://threads.example/football",
                author_handle="sports",
                created_at="2026-07-01T00:00:00Z",
                raw_text="Mbappe could just delay his run, like every other striker.",
                normalized_text="mbappe could just delay his run like every other striker",
                detected_language_mix="en",
                category="transport",
                subcategory="rail",
                entity="",
                location="",
                state="",
                severity="medium",
                confidence=0.5,
                engagement="",
                cluster_id="transport:delay",
            ),
            ComplaintSchema(
                source_platform="threads",
                post_id="telco",
                url="https://threads.example/telco",
                author_handle="legacy",
                created_at="2026-07-01T00:00:00Z",
                raw_text="Unifi down in Shah Alam",
                normalized_text="unifi down in shah alam",
                detected_language_mix="en",
                category="telco_internet",
                subcategory="outage",
                entity="Unifi",
                location="Shah Alam",
                state="Selangor",
                severity="high",
                confidence=0.5,
                engagement="",
                cluster_id="telco_internet:Unifi:Shah Alam:outage",
            ),
        ]
    )

    assert prune_rejected_threads_complaints() == 2

    with connect() as conn:
        rows = conn.execute("SELECT post_id FROM complaints ORDER BY post_id").fetchall()
    assert [row["post_id"] for row in rows] == ["valid"]


def test_transform_rows_does_not_treat_duration_as_bus_route():
    rows = transform_rows(
        {
            "threads": [
                {
                    "source_platform": "threads",
                    "post_id": "duration",
                    "url": "https://threads.example/duration",
                    "author_handle": "test",
                    "created_at": _today_iso(),
                    "raw_text": "RapidKL delay again, waited 1 hour 11 minutes for the van today",
                    "query": "rapidkl delay",
                    "seed_category": "transport",
                }
            ]
        }
    )
    assert len(rows) == 1
    assert rows[0].entity != "11"


def test_transform_rows_assigns_state_for_jb_sentral():
    rows = transform_rows(
        {
            "reddit": [
                {
                    "source_platform": "reddit",
                    "post_id": "r-jb",
                    "url": "https://old.reddit.com/r/johor/comments/example",
                    "author_handle": "reddit:test",
                    "created_at": _today_iso(4),
                    "raw_text": "KTM komuter delay at JB Sentral again this morning, train stuck for 40 minutes",
                    "query": "jb sentral train",
                    "seed_category": "transport",
                }
            ]
        }
    )
    assert len(rows) == 1
    assert rows[0].location == "JB Sentral"
    assert rows[0].state == "Johor"


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


def test_transform_rows_accepts_official_bus_mass_alert():
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

    assert len(rows) == 1
    assert rows[0].entity == "RapidKL Bus"
    assert rows[0].subcategory == "bus"
    assert rows[0].severity == "medium"


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
    threads_ts = _today_iso(4).replace("Z", ".000Z")
    reddit_ts = _today_iso(1).replace("Z", "+00:00")
    rows = transform_rows(
        {
            "threads": [
                {
                    "source_platform": "threads",
                    "post_id": "t-ts",
                    "url": "https://threads.example/post/1",
                    "author_handle": "threads:test",
                    "created_at": threads_ts,
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
                    "created_at": reddit_ts,
                    "raw_text": "LRT3 Shah Alam Line train stuck near Glenmarie right now, delay ongoing",
                    "query": "kelana jaya line delay",
                    "seed_category": "transport",
                }
            ],
        }
    )

    assert len(rows) == 2
    assert rows[0].created_at or rows[1].created_at
    assert {row.created_at for row in rows} == {
        threads_ts,
        reddit_ts,
    }
