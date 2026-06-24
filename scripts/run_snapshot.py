from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime import bootstrap_repo_root
from app.services.ingest_service import run_ingest
from scripts.audit_sources import write_source_audit_snapshot
from scripts.generate_trend_report import build_trend_payload, write_trend_report
from scripts.export_decision_memo import write_decision_memo_from_data
from app.db.session import fetch_category_counts
from app.services.scoring_service import score_categories


if __name__ == "__main__":
    bootstrap_repo_root()
    ingest = run_ingest()
    trend_payload = build_trend_payload(ingest)
    audit_path = write_source_audit_snapshot(ingest)
    trend_path = write_trend_report(ingest)
    write_decision_memo_from_data(
        ingest=ingest,
        trends=trend_payload["trends"],
        scores=score_categories(),
        raw_mix=fetch_category_counts(),
    )
    print(audit_path)
    print(trend_path)
