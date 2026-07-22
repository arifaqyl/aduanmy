from datetime import UTC, date, datetime, timedelta, timezone

from app.db.session import reset_complaints, upsert_complaints
from app.schemas.complaint import ComplaintSchema
from app.services.line_status_service import get_line_status_board


def _recent_ts() -> str:
    return datetime.now(UTC).isoformat()


def test_line_status_board_maps_kelana_complaint():
    reset_complaints()
    myt = timezone(timedelta(hours=8))
    mid_morning = datetime(2026, 7, 1, 10, 0, tzinfo=myt).astimezone(UTC)
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/t1",
                author_handle="k.sam95",
                created_at=mid_morning.isoformat(),
                raw_text="Kelana Jaya LRT line delay again stuck at Bangsar",
                normalized_text="kelana jaya lrt line delay again stuck at bangsar",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Bangsar",
                subcategory="rail",
                severity="medium",
                confidence=0.8,
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            )
        ]
    )

    board = get_line_status_board(now=mid_morning)
    kelana = next(line for line in board["lines"] if line["id"] == "kelana-jaya")
    assert kelana["status"] in {"delay", "minor", "disruption"}
    assert kelana["report_count"] >= 1
    assert board["active_line_count"] >= 1
    assert board["scope"] == "malaysia"


def test_line_status_board_corroborated_when_official_matches_line():
    reset_complaints()
    myt = timezone(timedelta(hours=8))
    mid_morning = datetime(2026, 7, 1, 10, 0, tzinfo=myt).astimezone(UTC)
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/t1",
                author_handle="commuter",
                created_at=mid_morning.isoformat(),
                raw_text="Kelana Jaya line delay stuck at Bangsar",
                normalized_text="kelana jaya line delay stuck at bangsar",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Bangsar",
                subcategory="rail",
                severity="medium",
                confidence=0.8,
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            ),
            ComplaintSchema(
                source_platform="official",
                post_id="o1",
                url="https://myrapid.com.my/alert",
                author_handle="official:myrapid",
                created_at=mid_morning.isoformat(),
                raw_text="Kelewatan Tren: Laluan Kelana Jaya",
                normalized_text="kelewatan tren laluan kelana jaya",
                detected_language_mix="ms",
                category="transport",
                entity="Kelana Jaya Line",
                location="",
                severity="low",
                confidence=0.2,
                cluster_id="transport:official:kelana",
            ),
        ]
    )

    board = get_line_status_board(now=mid_morning)
    kelana = next(line for line in board["lines"] if line["id"] == "kelana-jaya")
    assert kelana["corroborated"] is True
    assert kelana["report_count"] >= 1
    assert kelana["signal"]
    assert kelana["signal"].get("location") == "Bangsar"
    assert kelana["signal"].get("issue")
    assert kelana["official_match"]
    assert "myrapid.com.my" in (kelana["official_match"].get("url") or "")


def test_line_status_board_expires_yesterday_myt_reports():
    reset_complaints()
    myt = timezone(timedelta(hours=8))
    yesterday_noon = datetime.now(myt).replace(hour=12, minute=0, second=0, microsecond=0) - timedelta(days=1)
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="old-delay",
                url="https://example.com/old",
                author_handle="commuter",
                created_at=yesterday_noon.astimezone(UTC).isoformat(),
                raw_text="Kelana Jaya line delayed yesterday",
                normalized_text="kelana jaya line delayed yesterday",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Bangsar",
                subcategory="rail",
                severity="medium",
                confidence=0.8,
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            )
        ]
    )

    board = get_line_status_board()
    kelana = next(line for line in board["lines"] if line["id"] == "kelana-jaya")
    assert kelana["status"] == "unknown"
    assert board["status_window_mode"] == "myt_calendar_day"
    assert board["active_line_count"] == 0
    assert "today" in board["board_summary"].lower()


def test_after_last_train_clears_todays_delay_board():
    reset_complaints()
    myt = timezone(timedelta(hours=8))
    evening = datetime(2026, 7, 1, 20, 0, tzinfo=myt).astimezone(UTC)
    after_close = datetime(2026, 7, 1, 23, 45, tzinfo=myt).astimezone(UTC)
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="t1",
                url="https://example.com/t1",
                author_handle="rider",
                created_at=evening.isoformat(),
                raw_text="Monorail delay stuck at Bukit Bintang",
                normalized_text="monorail delay stuck at bukit bintang",
                detected_language_mix="en",
                category="transport",
                entity="KL Monorail",
                location="Bukit Bintang",
                subcategory="rail",
                severity="medium",
                confidence=0.8,
                cluster_id="transport:KL Monorail:Bukit Bintang:delay",
            )
        ]
    )
    during = get_line_status_board(now=datetime(2026, 7, 1, 22, 0, tzinfo=myt).astimezone(UTC))
    mono = next(line for line in during["lines"] if line["id"] == "monorail")
    assert mono["status"] in {"delay", "minor", "disruption"}
    assert mono["in_service"] is True

    ended = get_line_status_board(now=after_close)
    mono = next(line for line in ended["lines"] if line["id"] == "monorail")
    assert mono["status"] == "unknown"
    assert mono["status_label"] == "Ended for today"
    assert mono["in_service"] is False
    assert ended["active_line_count"] == 0


def test_line_status_board_expires_old_reports_and_marks_absence_honestly():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="old-delay",
                url="https://example.com/old",
                author_handle="commuter",
                created_at=(datetime.now(UTC) - timedelta(hours=25)).isoformat(),
                raw_text="Kelana Jaya line delayed yesterday",
                normalized_text="kelana jaya line delayed yesterday",
                detected_language_mix="en",
                category="transport",
                entity="Kelana Jaya Line",
                location="Bangsar",
                subcategory="rail",
                severity="medium",
                confidence=0.8,
                cluster_id="transport:Kelana Jaya Line:Bangsar:delay",
            )
        ]
    )

    board = get_line_status_board()
    kelana = next(line for line in board["lines"] if line["id"] == "kelana-jaya")
    assert kelana["status"] == "unknown"
    assert board["status_window_mode"] == "myt_calendar_day"
    assert board["active_line_count"] == 0
    assert board["lines_tracked_count"] >= 15
    assert "board_summary" in board


def test_planned_services_are_not_live_lines():
    reset_complaints()
    board = get_line_status_board(as_of=date(2026, 6, 28))
    line_ids = {line["id"] for line in board["lines"]}
    planned_ids = {line["id"] for line in board["planned_services"]}
    assert "lrt3" not in line_ids
    assert "ecrl" not in line_ids
    assert {"lrt3", "ecrl", "rts-johor"} <= planned_ids


def test_lrt_shah_alam_moves_to_live_board_on_service_date():
    reset_complaints()
    board = get_line_status_board(as_of=date(2026, 6, 29))
    line_ids = {line["id"] for line in board["lines"]}
    planned_ids = {line["id"] for line in board["planned_services"]}
    assert "lrt3" in line_ids
    assert "lrt3" not in planned_ids
    lrt3 = next(line for line in board["lines"] if line["id"] == "lrt3")
    assert lrt3["status"] == "unknown"
