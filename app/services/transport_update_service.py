from __future__ import annotations

import math
from datetime import date

from app.core.files import load_yaml


def _as_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)) if value else None


def get_transport_updates(*, today: date | None = None) -> dict:
    current = today or date.today()
    items = load_yaml("transport_updates.yaml").get("updates", [])
    active, upcoming = [], []
    for item in items:
        start = _as_date(item.get("valid_from"))
        end = _as_date(item.get("valid_to"))
        row = dict(item)
        if start:
            row["valid_from"] = start.isoformat()
        if end:
            row["valid_to"] = end.isoformat()
        row["status"] = "upcoming" if start and current < start else "active"
        row["ending_soon"] = bool(end and 0 <= (end - current).days <= 7)
        if end and current > end:
            continue
        (upcoming if row["status"] == "upcoming" else active).append(row)
    active.sort(key=lambda row: (not row.get("featured", False), str(row.get("valid_to") or "9999-12-31")))
    upcoming.sort(key=lambda row: str(row.get("valid_from") or "9999-12-31"))
    return {"product": "TrafficMY", "as_of": current.isoformat(), "active": active, "upcoming": upcoming}


def compare_rapid_passes(*, rides_per_month: int, average_fare: float, malaysian: bool, student: bool) -> dict:
    rides = max(1, min(int(rides_per_month), 200))
    fare = max(0.5, min(float(average_fare), 20.0))
    payg = round(rides * fare, 2)
    options = [{"id": "payg", "name": "Pay as you go", "monthly_cost": payg, "eligible": True}]
    if student and malaysian:
        options.append(
            {
                "id": "rapid-pelajar",
                "name": "Rapid Pelajar",
                "monthly_cost": round(payg * 0.5, 2),
                "eligible": True,
                "note": "Up to 50% off regular Rapid KL fares; annual eligibility renewal applies.",
                "url": "https://myrapid.com.my/our-products/rapidpelajar/",
            }
        )
    options.append(
        {
            "id": "my50",
            "name": "My50",
            "monthly_cost": 50.0,
            "eligible": malaysian,
            "break_even_rides": math.ceil(50 / fare),
            "note": "30 days of unlimited Rapid KL rail and bus rides for Malaysians.",
            "url": "https://myrapid.com.my/our-products/my50/",
        }
    )
    options.append(
        {
            "id": "rapid-bulanan",
            "name": "Rapid Bulanan",
            "monthly_cost": 150.0,
            "eligible": True,
            "break_even_rides": math.ceil(150 / fare),
            "note": "30 days unlimited on Rapid KL for all users.",
            "url": "https://myrapid.com.my/our-products/rapidbulananpass/",
        }
    )
    eligible = [option for option in options if option["eligible"]]
    best = min(eligible, key=lambda option: option["monthly_cost"])
    return {
        "rides_per_month": rides,
        "average_fare": fare,
        "payg_cost": payg,
        "options": options,
        "recommendation": best,
        "estimated_saving": round(max(0, payg - best["monthly_cost"]), 2),
        "note": "Estimate only. My50 and Rapid passes do not cover KTM or KLIA Ekspres/Transit.",
    }
