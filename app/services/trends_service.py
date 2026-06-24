from __future__ import annotations

import re
from collections import Counter

from app.db.session import connect, init_db
from app.pipeline.extract import extract_location

STOPWORDS = {
    "the",
    "and",
    "for",
    "that",
    "this",
    "with",
    "from",
    "have",
    "been",
    "just",
    "your",
    "please",
    "lagi",
    "yang",
    "dah",
    "tak",
    "boleh",
    "kat",
    "dan",
    "untuk",
    "ni",
    "itu",
    "aku",
    "saya",
    "nak",
    "pula",
    "sudah",
    "still",
    "very",
    "more",
    "about",
    "what",
    "when",
    "why",
    "which",
    "these",
    "them",
    "had",
    "one",
    "now",
    "time",
    "form",
    "line",
    "hi",
    "bij",
    "issue",
    "problem",
    "pending",
    "error",
    "down",
    "was",
    "are",
    "they",
    "you",
    "not",
    "all",
    "but",
    "into",
    "their",
    "after",
    "also",
    "there",
    "will",
    "than",
    "same",
    "then",
    "again",
    "today",
    "week",
    "already",
    "year",
    "out",
    "service",
    "services",
    "support",
    "official",
    "government",
    "malaysia",
    "grab",
    "account",
    "accounts",
    "face",
    "photo",
    "month",
    "months",
    "need",
    "needs",
    "any",
    "app",
    "apps",
    "hello",
    "hi",
    "try",
    "using",
    "used",
    "renew",
    "renewal",
    "roadtax",
    "driver",
    "drivers",
    "about",
    "right",
    "like",
    "ask",
    "askrapidkl",
    "myrapidkl",
    "finally",
    "oops",
    "exact",
    "maybe",
    "really",
    "luck",
    "image",
    "images",
    "neighbor",
    "happening",
    "experiencing",
    "report",
    "made",
    "said",
    "resolve",
    "yesterday",
    "house",
    "hours",
    "dari",
    "semakan",
    "trip",
    "sebelum",
    "bergerak",
    "pada",
    "masa",
    "ini",
    "hanya",
    "sebuah",
    "beroperasi",
    "update",
    "tren",
    "laluan",
    "train",
    "delays",
    "perkhidmatan",
    "perantara",
    "process",
    "has",
    "experience",
    "new",
    "phone",
    "didn",
    "point",
    "anyone",
    "already",
    "almost",
    "home",
    "around",
    "keep",
    "keeps",
    "work",
    "works",
    "know",
    "next",
    "replying",
    "share",
    "matter",
    "further",
    "improvement",
    "caused",
    "contact",
    "residenti",
    "at",
    "in",
    "on",
    "or",
    "to",
    "of",
    "is",
    "it",
    "we",
    "our",
    "via",
    "can",
    "get",
    "they",
    "astro",
    "hbo",
    "channel",
    "channels",
    "movie",
    "movies",
    "broadcasting",
    "disney",
    "netflix",
    "premier",
    "league",
    "showtime",
    "cinemax",
    "owned",
    "before",
    "last",
    "would",
    "its",
    "rapid",
    "maaf",
    "atas",
    "akan",
    "gerak",
}


def _tokenize(text: str) -> list[str]:
    cleaned = re.sub(r"@\w+", " ", text.lower())
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{2,}", cleaned)
    return [token for token in tokens if token not in STOPWORDS]


def _row_dynamic_stopwords(row: dict) -> set[str]:
    blocked: set[str] = set()
    entity = (row.get("entity") or "").lower()
    location = (row.get("location") or "").lower()
    for part in re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{1,}", entity):
        blocked.add(part)
    for part in re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{1,}", location):
        blocked.add(part)
    extracted_location = extract_location(row.get("normalized_text", ""))
    for part in re.findall(r"[a-zA-Z][a-zA-Z0-9_+-]{1,}", extracted_location.lower()):
        blocked.add(part)
    return blocked


def _term_mining_rows(rows: list[dict]) -> list[dict]:
    blocked_telco_terms = {"astro", "hbo", "channel", "channels", "broadcasting", "movie", "movies"}
    out: list[dict] = []
    for row in rows:
        if row["source_platform"] == "official":
            continue
        if row.get("severity") == "low":
            continue
        text = row.get("normalized_text", "").lower()
        if row.get("category") == "telco_internet" and sum(term in text for term in blocked_telco_terms) >= 2:
            continue
        out.append(row)
    return out


def get_trends(limit_terms: int = 12) -> dict:
    init_db()
    with connect() as conn:
        rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT source_platform, category, entity, location, severity,
                       created_at, normalized_text, url
                FROM complaints
                ORDER BY inserted_at DESC, id DESC
                """
            )
        ]

    social_rows = [row for row in rows if row["source_platform"] != "official"]
    grounding_rows = [row for row in rows if row["source_platform"] == "official"]
    entity_counts = Counter(row["entity"] for row in social_rows if row["entity"])
    location_counts = Counter(row["location"] for row in social_rows if row["location"])
    category_counts = Counter(row["category"] for row in social_rows if row["category"])
    severity_counts = Counter(row["severity"] for row in rows if row["severity"])
    term_rows = _term_mining_rows(rows)
    term_counts: Counter[str] = Counter()
    for row in term_rows:
        dynamic_stopwords = _row_dynamic_stopwords(row)
        tokens = [token for token in _tokenize(row.get("normalized_text", "")) if token not in dynamic_stopwords]
        term_counts.update(tokens)

    freshest = [
        {
            "category": row["category"],
            "entity": row["entity"],
            "location": row["location"],
            "severity": row["severity"],
            "created_at": row["created_at"],
            "url": row["url"],
            "text": row["normalized_text"][:220],
        }
        for row in social_rows[:8]
    ]

    return {
        "totals": {
            "complaints": len(social_rows),
            "grounding_rows": len(grounding_rows),
            "categories": len(category_counts),
            "entities": len(entity_counts),
            "locations": len(location_counts),
        },
        "top_categories": [{"name": name, "count": count} for name, count in category_counts.most_common()],
        "top_entities": [{"name": name, "count": count} for name, count in entity_counts.most_common(10)],
        "top_locations": [{"name": name, "count": count} for name, count in location_counts.most_common(10)],
        "top_terms": [{"term": name, "count": count} for name, count in term_counts.most_common(limit_terms)],
        "severity_mix": [{"severity": name, "count": count} for name, count in severity_counts.most_common()],
        "freshest": freshest,
    }
