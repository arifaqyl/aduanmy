from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.runtime import bootstrap_repo_root
from app.services.trends_service import get_trends
from app.services.scoring_service import score_categories
from app.db.session import fetch_category_counts
from app.core.files import report_path


def _load_ingest_summary() -> dict:
    path = report_path("latest_ingest_summary.json")
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        required = {"written", "threads", "reddit", "x", "official"}
        if required.issubset(data):
            return data
    from app.services.ingest_service import run_ingest

    return run_ingest()


def _current_recommendation(scores: list[dict]) -> tuple[str, str]:
    if not scores:
        return "undecided", "No category scores available yet."
    top = scores[0]["category"]
    if top == "transport":
        return "TrafficMY", "Strongest density, best source diversity, and the cleanest verification/demo story."
    if top == "telco_internet":
        return "ServiceOutageMY", "Clear outage language and recognizable providers make this the strongest fallback."
    if top == "gov_portals":
        return "PortalWatchMY", "Portal/app failures are legible, but the evidence base is still thinner than transport."
    return top, "Current top category by score, but still needs tighter evidence before branding."


def write_decision_memo() -> Path:
    ingest = _load_ingest_summary()
    return write_decision_memo_from_data(
        ingest=ingest,
        trends=get_trends(),
        scores=score_categories(),
        raw_mix=fetch_category_counts(),
    )


def write_decision_memo_from_data(
    *,
    ingest: dict,
    trends: dict,
    scores: list[dict],
    raw_mix: list,
) -> Path:
    lines = [
        "# AduanMY Decision Memo",
        "",
        "Based on the latest verified local ingest.",
        "",
        "## Source Reality",
        f"- Full ingest loop now completes in about `{max(ingest.get('timings', {}).values() or [0])}s` with parallel collectors.",
        "- Threads is the strongest open discovery-style social source in the repo.",
        "- X works as a targeted service-account monitoring lane, not a broad search lane.",
        "- Reddit is usable but still noisier than Threads/X.",
        "- Official pages are grounding rails, not complaint-density rails.",
        "",
        "## Current Counts",
        f"- stored complaint rows: `{ingest['written']}`",
        "- raw source rows:",
        f"  - Threads: `{ingest['threads']}`",
        f"  - Reddit: `{ingest['reddit']}`",
        f"  - X: `{ingest['x']}`",
        f"  - Official: `{ingest['official']}`",
        "",
        "## Current Category Shape",
        *[f"- {item['name']}: {item['count']}" for item in trends["top_categories"]],
        "",
        "## Scorecard",
    ]
    for row in raw_mix:
        lines.append(f"- raw mix: {row['category']} | {row['source_platform']} | volume={row['volume']}")
    lines.extend(["", "## Ranked Categories"])
    for row in scores:
        lines.append(f"- `{row['category']}`")
        lines.append(f"  - density: `{row['source_density']}`")
        lines.append(f"  - source_diversity: `{row['source_diversity']}`")
        lines.append(f"  - verification_potential: `{row['verification_potential']}`")
        lines.append(f"  - demo_value: `{row['demo_value']}`")
        lines.append(f"  - total: `{row['total']}`")
    recommendation, why = _current_recommendation(scores)
    if scores:
        lines.extend(
            [
                "",
                "## Recommendation If Choosing Today",
                f"Primary wedge: `{recommendation}`",
                "",
                "Why:",
                f"- {why}",
                "- transport and telco are the only categories with a credible verification/demo path right now.",
                "- banking/payments is no longer strong enough after stricter filtering.",
                "",
                "## Second Choice",
                "- `ServiceOutageMY` if telco overtakes transport in a later snapshot.",
                "",
                "## Not Recommended Yet",
                "- broad `AduanMY` as the shipped product name for v1",
                "- `banking_payments` because the trust story is still weak",
                "- `gov_portals` because the live evidence base is still too thin",
                "",
                "## Decision",
                f"If a narrower product build started next, build `{recommendation}` first.",
            ]
        )
    target = report_path("decision_memo.md")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    bootstrap_repo_root()
    print(write_decision_memo())
