from __future__ import annotations

from collections import defaultdict

from app.db.session import fetch_category_counts


def score_categories() -> list[dict[str, int | str]]:
    rows = fetch_category_counts()
    grouped: dict[str, dict[str, int]] = defaultdict(dict)
    for row in rows:
        grouped[row["category"]][row["source_platform"]] = int(row["volume"])
    scored: list[dict[str, int | str]] = []
    for category, by_source in grouped.items():
        social_sources = {source: count for source, count in by_source.items() if source != "official"}
        source_density = sum(social_sources.values())
        source_diversity = len(social_sources)
        verification_potential = 2 if "official" in by_source else 0
        demo_value = 2 if category in {"transport", "telco_internet", "gov_portals"} else 1
        realtime_provider_bonus = 2 if "x" in social_sources and "official" in by_source else 0
        total = source_density + source_diversity + verification_potential + demo_value + realtime_provider_bonus
        scored.append(
            {
                "category": category,
                "source_density": source_density,
                "source_diversity": source_diversity,
                "verification_potential": verification_potential,
                "demo_value": demo_value,
                "realtime_provider_bonus": realtime_provider_bonus,
                "total": total,
            }
        )
    return sorted(scored, key=lambda item: int(item["total"]), reverse=True)
