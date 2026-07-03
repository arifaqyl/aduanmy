from __future__ import annotations

import re

RAIL_LINE_HINTS = (
    "kelana jaya",
    "ampang",
    "sri petaling",
    "kajang line",
    "putrajaya line",
    "monorel",
    "monorail",
    "lrt ",
    "mrt ",
    "lrt3",
    "lrt 3",
    "shah alam",
    "ets",
    "klia",
    "erl",
    "laluan kelana",
    "laluan ampang",
    "laluan kajang",
    "laluan putrajaya",
)

BUS_ALERT_PATTERNS = [
    re.compile(r"kelewatan\s+bas\s*:\s*(\d+)\s*laluan", re.I),
    re.compile(r"(\d+)\s*laluan\s+terjejas", re.I),
    re.compile(r"kelewatan\s+bas", re.I),
    re.compile(r"bas\s+terjejas", re.I),
    re.compile(r"bas\s+perantara", re.I),
    re.compile(r"next\s+bas", re.I),
    re.compile(r"sebuah\s+bas", re.I),
]


def is_mass_bus_alert(text: str) -> bool:
    low = text.lower()
    return any(p.search(low) for p in BUS_ALERT_PATTERNS[:4])


def is_rail_line_alert(text: str) -> bool:
    low = text.lower()
    if is_mass_bus_alert(text) and not any(h in low for h in RAIL_LINE_HINTS):
        return False
    return any(h in low for h in RAIL_LINE_HINTS)


def parse_myrapid_official(text: str) -> dict:
    low = text.lower()
    out: dict = {}

    for pattern in BUS_ALERT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        out["subcategory"] = "bus"
        out["entity"] = "RapidKL Bus"
        if match.groups() and match.group(1).isdigit():
            count = int(match.group(1))
            out["severity"] = "high" if count >= 8 else "medium"
            out["affected_routes"] = count
        elif "perantara" in low:
            out["entity"] = "RapidKL Shuttle"
            out["severity"] = "medium"
        else:
            out["severity"] = "medium"
        if "penang" in low:
            out["entity"] = "Penang Rapid"
            out["state"] = "Penang"
        elif "kuantan" in low:
            out["entity"] = "Rapid Kuantan"
            out["state"] = "Pahang"
        else:
            out["state"] = "Wilayah Persekutuan"
        break

    if not out and is_rail_line_alert(text):
        out["subcategory"] = "rail"
        out["severity"] = "low"

    freq = re.search(r"kemas\s+kin[i]?\s+kekerapan", low)
    if freq and "monorel" in low:
        out.setdefault("subcategory", "rail")
        out.setdefault("entity", "KL Monorail Line")
        out.setdefault("severity", "medium")

    return out


def classify_transport_mode(*, text: str, entity: str = "", subcategory: str = "") -> str:
    if subcategory in {"bus", "rail"}:
        return subcategory
    low = f"{text} {entity}".lower()
    if is_mass_bus_alert(low) or any(t in low for t in ["rapid penang", "rapid kuala", "feeder bus", "bas rapid"]):
        return "bus"
    if any(t in low for t in [" lrt", " mrt", "ktm", "ktmb", "monorail", "monorel", "line", "tren"]):
        return "rail"
    if entity and "bus" in entity.lower():
        return "bus"
    return ""
