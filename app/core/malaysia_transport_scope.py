"""Malaysia-only transport scope for TrafficMY (exclude foreign transit noise)."""
from __future__ import annotations

import re


def _token_hit(token: str, blob: str) -> bool:
    """Plain substring matching lets short tokens like "ktm" false-positive
    inside unrelated compounds/handles (e.g. "ktm_switzerland"). Multi-word
    phrases already have natural boundaries via spaces; single-word tokens
    get a regex word boundary that also treats "_" as a separator."""
    if " " in token:
        return token in blob
    return re.search(r"(?<![a-z0-9_])" + re.escape(token) + r"(?![a-z0-9_])", blob) is not None

# Overseas systems — reject when no Malaysia anchor present.
FOREIGN_TRANSPORT_BLOCKERS = [
    "smrt",
    "singapore mrt",
    "sbs transit",
    "land transport authority",
    "lta singapore",
    "mytransport.sg",
    "bts bangkok",
    "mrt bangkok",
    "bangkok bts",
    "hk mtr",
    "hong kong mtr",
    "taiwan mrt",
    "taipei metro",
    "mrt taipei",
    "tokyo metro",
    "jr east",
    "seoul metro",
    "transjakarta",
    "jakarta mrt",
]

MALAYSIA_TRANSPORT_SIGNALS = [
    "malaysia",
    "malaysian",
    "kuala lumpur",
    "kl sentral",
    "wilayah persekutuan",
    "selangor",
    "penang",
    "johor",
    "sabah",
    "sarawak",
    "rapidkl",
    "rapid kl",
    "myrapidkl",
    "askrapidkl",
    "prasarana",
    "ktm",
    "ktmb",
    "komuter",
    "kelana jaya",
    "laluan kelana",
    "ampang line",
    "laluan ampang",
    "sri petaling",
    "kajang line",
    "putrajaya line",
    "mrt kajang",
    "mrt putrajaya",
    "lrt3",
    "lrt 3",
    "shah alam lrt",
    "ecrl",
    "east coast rail",
    "penang rapid",
    "rapid penang",
    "jb sentral",
    "rts link",
    "rts johor",
    "johor bahru",
    "bas rapid",
    "monorail",
    "monorel",
    "pasar seni",
    "bangsar",
    "klang valley",
]

GENERIC_TRANSPORT_ENTITIES = {
    "lrt",
    "mrt",
    "train",
    "tren",
    "bus",
    "bas",
    "line",
    "transit",
}

STRICT_MALAYSIA_TRANSPORT_SIGNALS = [
    token
    for token in MALAYSIA_TRANSPORT_SIGNALS
    if token not in {"monorail"}
]
STRICT_MALAYSIA_TRANSPORT_SIGNALS.extend(
    [
        "lrt kj",
        "kj line",
        "kjl",
        "laluan kj",
        "mrt kwasa",
        "kwasa damansara",
        "masjid jamek",
        "chan sow lin",
        "ara damansara",
        "glenmarie",
        "putra heights",
        "bandar utama",
        "trx",
        "maluri",
    ]
)

MALAYSIAN_STATES = {
    "johor",
    "kedah",
    "kelantan",
    "melaka",
    "negeri sembilan",
    "pahang",
    "penang",
    "perak",
    "perlis",
    "pulau pinang",
    "sabah",
    "sarawak",
    "selangor",
    "terengganu",
    "wilayah persekutuan",
}


def is_malaysia_transport_text(
    text: str,
    *,
    entity: str = "",
    location: str = "",
    state: str = "",
) -> bool:
    blob = " ".join([text, entity, location, state]).lower()
    if not blob.strip():
        return False

    foreign_hit = any(_token_hit(token, blob) for token in FOREIGN_TRANSPORT_BLOCKERS)
    malaysia_hit = any(_token_hit(token, blob) for token in MALAYSIA_TRANSPORT_SIGNALS)
    state_hit = state.lower() in MALAYSIAN_STATES if state else False

    if foreign_hit and not (malaysia_hit or state_hit):
        return False
    if malaysia_hit or state_hit:
        return True

    # Collectors are MY-focused; generic rail/bus terms without foreign anchor are OK.
    generic_my = any(
        _token_hit(token, blob)
        for token in ["lrt", "mrt", "ktm", "komuter", "rapid", "tren", "bas rapid", "gangguan"]
    )
    return generic_my and not foreign_hit


def has_strict_malaysia_transport_anchor(
    text: str,
    *,
    entity: str = "",
    location: str = "",
    state: str = "",
) -> bool:
    """Threads-grade scope: reject global/generic "delay + line" text."""
    blob = " ".join([text, entity, location, state]).lower()
    if not blob.strip():
        return False

    if state and state.lower() in MALAYSIAN_STATES:
        return True
    if location:
        return True

    entity_low = entity.lower().strip()
    if entity_low and entity_low not in GENERIC_TRANSPORT_ENTITIES:
        return True

    return any(_token_hit(token, blob) for token in STRICT_MALAYSIA_TRANSPORT_SIGNALS)


def is_malaysia_transport_cluster(cluster: dict) -> bool:
    sources = {
        part.strip()
        for part in (cluster.get("sources") or "").split(",")
        if part.strip()
    }
    if sources == {"gtfs_rt"}:
        return True
    return is_malaysia_transport_text(
        cluster.get("example_text") or "",
        entity=cluster.get("entity") or "",
        location=cluster.get("location") or "",
        state=cluster.get("state") or "",
    )
