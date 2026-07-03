from app.db.session import init_db, prune_old_complaints, reset_complaints, upsert_complaints
from app.schemas.complaint import ComplaintSchema


def test_upsert_accumulates_without_reset():
    reset_complaints()
    first = upsert_complaints(
        [
            ComplaintSchema(
                source_platform="x",
                post_id="a",
                url="https://example.com/a",
                author_handle="u",
                created_at="2026-06-22T00:00:00Z",
                raw_text="LRT delay",
                normalized_text="lrt delay",
                category="transport",
                entity="LRT",
                cluster_id="transport:LRT:delay",
            )
        ]
    )
    second = upsert_complaints(
        [
            ComplaintSchema(
                source_platform="reddit",
                post_id="b",
                url="https://example.com/b",
                author_handle="u",
                created_at="2026-06-23T00:00:00Z",
                raw_text="KTM delay jb sentral",
                normalized_text="ktm delay jb sentral",
                category="transport",
                entity="KTM",
                state="Johor",
                cluster_id="transport:KTM:Johor:delay",
            )
        ]
    )
    init_db()
    from app.db.session import connect

    with connect() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM complaints").fetchone()["c"]
    assert first == 1
    assert second == 1
    assert count == 2


def test_prune_old_complaints(monkeypatch):
    from app.core.config import settings

    reset_complaints()
    upsert_complaints(
        [
            ComplaintSchema(
                source_platform="x",
                post_id="old",
                url="https://example.com/old",
                author_handle="u",
                created_at="2020-01-01T00:00:00Z",
                raw_text="old signal",
                normalized_text="old signal",
                category="transport",
                cluster_id="transport:old",
            )
        ]
    )
    monkeypatch.setattr(settings, "retention_days", 90)
    removed = prune_old_complaints()
    assert removed == 1
