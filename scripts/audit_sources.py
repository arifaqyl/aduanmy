import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime import bootstrap_repo_root
from app.db.session import connect
from app.core.files import raw_path, report_path
from app.services.ingest_service import run_ingest


def write_source_audit_snapshot(ingest_report: dict | None = None) -> Path:
    if ingest_report is None:
        ingest_report = run_ingest()
    collected = json.loads(raw_path("latest_sample.json").read_text(encoding="utf-8"))
    with connect() as conn:
        stored_by_source = {
            row["source_platform"]: row["volume"]
            for row in conn.execute(
                """
                SELECT source_platform, COUNT(*) AS volume
                FROM complaints
                GROUP BY source_platform
                ORDER BY source_platform
                """
            )
        }
        stored_by_category = [
            dict(row)
            for row in conn.execute(
                """
                SELECT category, source_platform, COUNT(*) AS volume
                FROM complaints
                GROUP BY category, source_platform
                ORDER BY category, source_platform
                """
            )
        ]
    lines = [
        "# Source Audit Snapshot",
        "",
        "## Ingest Summary",
        f"- written_to_db: {ingest_report['written']}",
        f"- raw_threads: {ingest_report['threads']}",
        f"- raw_reddit: {ingest_report['reddit']}",
        f"- raw_x: {ingest_report['x']}",
        f"- raw_official: {ingest_report['official']}",
        "",
        "## Stored Complaint Rows By Source",
        *[f"- {source}: {count}" for source, count in sorted(stored_by_source.items())],
        "",
    ]
    for source, rows in collected.items():
        lines.append(f"## {source}")
        lines.append(f"- sample_count: {len(rows)}")
        if rows:
            lines.append(f"- first_example: {rows[0]['raw_text'][:180]}")
        else:
            lines.append("- first_example: none")
        lines.append("")
    lines.extend(
        [
            "## Stored Complaint Rows By Category and Source",
            *[
                f"- {row['category']} | {row['source_platform']} | {row['volume']}"
                for row in stored_by_category
            ],
            "",
            "## Notes",
            "- This snapshot distinguishes raw collection count from complaint rows that survive filtering.",
            "- Official pages are grounding sources; they help verification but are not high-density complaint feeds.",
            "- X now uses targeted public profile discovery plus exact status-page fetches for selected service accounts.",
            "- Raw source counts can vary slightly between runs because public search and profile surfaces are live.",
            "",
        ]
    )
    target = report_path("source_audit_snapshot.md")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report_path("source_audit_snapshot.json").write_text(
        json.dumps(
            {
                "ingest": ingest_report,
                "stored_by_source": stored_by_source,
                "stored_by_category": stored_by_category,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return target


if __name__ == "__main__":
    bootstrap_repo_root()
    print(write_source_audit_snapshot())
