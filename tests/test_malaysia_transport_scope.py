from app.core.malaysia_transport_scope import (
    is_malaysia_transport_cluster,
    is_malaysia_transport_text,
)
from app.db.session import reset_complaints, upsert_complaints
from app.schemas.complaint import ComplaintSchema
from app.services.line_status_service import LINE_CATALOG, get_line_status_board


def test_malaysia_scope_accepts_kelana_and_ktm():
    assert is_malaysia_transport_text("Kelana Jaya LRT line delay stuck at Bangsar today")
    assert is_malaysia_transport_text("KTM komuter delay at KL Sentral this morning")
    assert is_malaysia_transport_text("MRT Kajang line delay ke rapidkl")


def test_malaysia_scope_rejects_foreign_only():
    assert not is_malaysia_transport_text("SMRT breakdown on Singapore MRT North-South line")
    assert not is_malaysia_transport_text("BTS Bangkok skytrain delay at Siam station")
    assert not is_malaysia_transport_text("Hong Kong MTR Tung Chung line suspended")


def test_malaysia_scope_allows_foreign_comparison_with_malaysia_anchor():
    assert is_malaysia_transport_text(
        "KL MRT delay again — not like Singapore SMRT which is more reliable",
        entity="Kajang Line",
    )


def test_line_board_includes_multiple_malaysia_lines():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="lrt",
                url="https://example.com/lrt",
                author_handle="u1",
                created_at=datetime.now(UTC).isoformat(),
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
            ),
            ComplaintSchema(
                source_platform="threads",
                post_id="mrt",
                url="https://example.com/mrt",
                author_handle="u2",
                created_at=datetime.now(UTC).isoformat(),
                raw_text="MRT Putrajaya line delay ke rapidkl oiii hari ni",
                normalized_text="mrt putrajaya line delay ke rapidkl oiii hari ni",
                detected_language_mix="en",
                category="transport",
                entity="Putrajaya Line",
                location="Putrajaya",
                subcategory="rail",
                severity="medium",
                confidence=0.8,
                cluster_id="transport:RapidKL:Putrajaya:delay",
            ),
            ComplaintSchema(
                source_platform="threads",
                post_id="ktm",
                url="https://example.com/ktm",
                author_handle="u3",
                created_at=datetime.now(UTC).isoformat(),
                raw_text="KTM to KL Sentral delay this morning, train stuck",
                normalized_text="ktm to kl sentral delay this morning train stuck",
                detected_language_mix="en",
                category="transport",
                entity="KTM",
                location="KL Sentral",
                subcategory="rail",
                severity="medium",
                confidence=0.8,
                cluster_id="transport:KL Sentral:KL Sentral:delay",
            ),
        ]
    )

    board = get_line_status_board()
    line_ids = {line["id"] for line in board["lines"]}
    assert "kelana-jaya" in line_ids
    assert "kajang-putrajaya" in line_ids
    assert "ktm-komuter" in line_ids
    assert len(LINE_CATALOG) >= 10
    assert board["scope"] == "malaysia"


def test_foreign_cluster_excluded_from_board():
    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="threads",
                post_id="sg",
                url="https://example.com/sg",
                author_handle="sguser",
                created_at=datetime.now(UTC).isoformat(),
                raw_text="Singapore MRT SMRT delay on North-South line today",
                normalized_text="singapore mrt smrt delay on north-south line today",
                detected_language_mix="en",
                category="transport",
                entity="SMRT",
                location="Singapore",
                severity="medium",
                confidence=0.5,
                cluster_id="transport:SMRT:Singapore:delay",
            ),
            ComplaintSchema(
                source_platform="threads",
                post_id="my",
                url="https://example.com/my",
                author_handle="k.sam95",
                created_at=datetime.now(UTC).isoformat(),
                raw_text="Kelana Jaya LRT line delay again stuck at Bangsar",
                normalized_text="kelana jaya lrt line delay again stuck at bangsar",
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

    board = get_line_status_board()
    report_ids = {r["cluster_id"] for r in board["recent_reports"]}
    assert "transport:SMRT:Singapore:delay" not in report_ids
    assert "transport:Kelana Jaya Line:Bangsar:delay" in report_ids
    assert not is_malaysia_transport_cluster(
        {
            "example_text": "Singapore MRT SMRT delay",
            "entity": "SMRT",
            "location": "Singapore",
            "sources": "threads",
        }
    )
from datetime import UTC, datetime
