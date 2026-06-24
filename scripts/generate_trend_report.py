from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime import bootstrap_repo_root
from app.core.files import report_path
from app.services.trends_service import get_trends


REQUIRED_INGEST_KEYS = {"written", "threads", "reddit", "x", "official"}


def _load_or_build_ingest(ingest: dict | None = None) -> dict:
    if ingest and REQUIRED_INGEST_KEYS.issubset(ingest):
        return ingest
    ingest_path = report_path("latest_ingest_summary.json")
    if ingest_path.exists():
        loaded = json.loads(ingest_path.read_text(encoding="utf-8"))
        if REQUIRED_INGEST_KEYS.issubset(loaded):
            return loaded
    from app.services.ingest_service import run_ingest

    return run_ingest()


def build_trend_payload(ingest: dict | None = None) -> dict:
    ingest = _load_or_build_ingest(ingest)
    trends = get_trends()
    return {"ingest": ingest, "trends": trends}


def write_trend_report(ingest: dict | None = None) -> Path:
    payload = build_trend_payload(ingest)
    ingest = payload["ingest"]
    trends = payload["trends"]
    report_path("latest_trends.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# Latest Trend Report",
        "",
        "## Ingest",
        f"- stored complaints: {ingest['written']}",
        f"- raw Threads: {ingest['threads']}",
        f"- raw Reddit: {ingest['reddit']}",
        f"- raw X: {ingest['x']}",
        f"- raw official: {ingest['official']}",
        "",
        "## Top Complaint Categories",
        *[f"- {item['name']}: {item['count']}" for item in trends["top_categories"]],
        "",
        "## Top Complaint Entities",
        *[f"- {item['name']}: {item['count']}" for item in trends["top_entities"]],
        "",
        "## Top Complaint Locations",
        *[f"- {item['name']}: {item['count']}" for item in trends["top_locations"]],
        "",
        "## Top Terms",
        *[f"- {item['term']}: {item['count']}" for item in trends["top_terms"]],
        "",
        "## Notes",
        f"- social complaint rows in trend summary: {trends['totals']['complaints']}",
        f"- official grounding rows excluded from density but available for verification: {trends['totals']['grounding_rows']}",
        "",
    ]
    target = report_path("latest_trends.md")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    bootstrap_repo_root()
    ingest = _load_or_build_ingest()
    print(write_trend_report(ingest))
