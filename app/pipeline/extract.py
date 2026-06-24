from __future__ import annotations

import re

from app.core.files import load_yaml

GENERIC_QUERY_TOKENS = {
    "boleh",
    "problem",
    "issue",
    "error",
    "pending",
    "road",
    "flood",
    "delay",
    "lambat",
    "line",
    "down",
    "outage",
    "rosak",
    "internet",
    "jam",
    "tak",
}

SHORT_ENTITY_TOKENS = {"lrt", "mrt", "ktm", "mae", "kwsp"}

TRANSPORT_ENTITY_ALIASES = [
    (
        "kajang/putrajaya lines",
        [
            "putrajaya, kajang mrt lines",
            "kajang, putrajaya mrt lines",
            "putrajaya and kajang mrt lines",
            "kajang and putrajaya mrt lines",
            "putrajaya, kajang lines",
            "kajang, putrajaya lines",
        ],
    ),
    ("ampang/sri petaling line", ["laluan ampang/sri petaling", "ampang/sri petaling line"]),
    (
        "ampang/sri petaling line",
        [
            "ampang and sri petaling lrt lines",
            "ampang sri petaling lrt lines",
            "services on the ampang and sri petaling lrt lines",
            "laluan ampang dan sri petaling",
        ],
    ),
    ("ampang line", ["laluan ampang", "ampang line"]),
    ("sri petaling line", ["laluan sri petaling", "sri petaling line"]),
    ("kelana jaya line", ["laluan kelana jaya", "kelana jaya line", "kelana jaya lrt line"]),
    ("kajang line", ["laluan kajang", "kajang line", "mrt kajang line"]),
    ("putrajaya line", ["laluan putrajaya", "putrajaya line", "mrt putrajaya line"]),
    ("kl monorail line", ["laluan monorel", "kl monorail line", "monorail line", "kl monorail"]),
]

LINE_LOCATION_BLOCKERS = [
    "laluan ampang/sri petaling",
    "ampang/sri petaling line",
    "ampang and sri petaling lrt lines",
    "laluan ampang dan sri petaling",
    "laluan ampang",
    "ampang line",
    "laluan sri petaling",
    "sri petaling line",
    "laluan kelana jaya",
    "kelana jaya line",
    "laluan kajang",
    "kajang line",
    "laluan putrajaya",
    "putrajaya line",
    "laluan monorel",
    "kl monorail line",
    "monorail line",
]

CATEGORY_REQUIRED_TOKENS = {
    "transport": [
        "delay",
        "lambat",
        "gangguan",
        "gangguan perkhidmatan",
        "incident",
        "fire alarm",
        "jejas",
        "jejas perkhidmatan",
        "kesulitan",
        "kelewatan",
        "train",
        "tren",
    ],
    "telco_internet": [
        "down",
        "outage",
        "tak boleh",
        "rosak",
        "internet",
        "line",
        "pending",
        "error",
        "problem",
        "issue",
        "no internet",
        "session expired",
        "unrecognized image",
    ],
    "banking_payments": [
        "transfer",
        "transaction",
        "withdraw",
        "payment",
        "account",
        "register",
        "login",
        "bank",
        "app",
        "duitnow",
        "ewallet",
        "salary",
    ],
    "gov_portals": [
        "portal",
        "app",
        "system",
        "login",
        "renew",
        "renewal",
        "permit",
        "roadtax",
        "jpj",
        "kwsp",
        "myeg",
    ],
    "flood_weather": [
        "banjir",
        "flood",
        "road closure",
        "jalan tutup",
        "hujan lebat",
        "landslide",
    ],
}

CATEGORY_BLOCKED_TOKENS = {
    "transport": [
        "for sale",
        "for rent",
        "asking price",
        "below market",
        "investment",
        "berminat boleh pm",
        "dm for viewing",
        "walkable walking distance",
        "walking distance",
        "corner lot",
        "apartment",
        "condo",
        "internship",
        "hiring",
        "fresh graduate",
        "breakfast",
        "cafe",
        "pastries",
        "hot meals",
        "serve reaaaally good",
        "fully furnished",
        "move-in ready",
        "accommodation provided",
        "salary:",
        "jobstreet",
        "message me today",
    ],
    "telco_internet": [
        "hbo",
        "astro",
        "cinemax",
        "showtime",
        "broadcasting",
        "disney",
        "netflix",
        "premier league",
        "channel",
        "channels",
        "movie",
        "movies",
        "property owner",
        "post-vp",
        "developer",
        "gsd land",
        "facial verification",
        "face not valid",
        "cooldown timer",
        "unrecognized image",
        "ekyc",
        "id check",
        "business phone number",
        "clear the app data",
    ],
    "banking_payments": [
        "career",
        "retirement",
        "graduate engineer",
        "mnc",
        "open account",
        "opening account",
        "business account",
        "savings account",
        "freelancing",
        "taxes",
        "tax advice",
        "unemployment",
    ],
    "gov_portals": [
        "citizenship",
        "divorce",
        "abusive",
        "lawyer",
        "visa issues",
        "grab evp",
        "e-hailing vehicle permit",
        "evp renewal",
        "driver partner",
    ],
    "flood_weather": [
        "ghost story",
        "spooky",
        "mercun",
        "kubur",
    ],
}

TRANSPORT_STRONG_INCIDENT_TERMS = [
    "delay",
    "delays",
    "lambat",
    "kelewatan",
    "gangguan",
    "jejas",
    "jejas perkhidmatan",
    "disruption",
    "incident",
    "fire alarm",
    "tak boleh keluar",
    "tak gerak",
    "tak gerak2",
    "tak bergerak",
    "kenape tak gerak",
    "berhenti lelama",
    "stuck",
    "stucked",
    "emergency brake",
    "brake failure",
    "brake failures",
    "technical fault",
    "technical issue",
    "track switch failure",
    "faulty train component",
    "door malfunction",
    "tak bukak",
    "pintu tak bukak",
    "disembark",
    "turun chan sow lin",
    "gap masa",
    "manual operation",
    "manually operated",
    "longer waiting times",
    "slower train movements",
]

TRANSPORT_WEAK_INCIDENT_TERMS = [
    "problem",
    "issues",
    "issue",
    "rosak",
    "ramai manusia",
    "queue mcm ukorr",
    "queue",
    "penuh",
    "hari2",
]

TRANSPORT_LIVE_CONTEXT_TERMS = [
    "hari ni",
    "harini",
    "pagi ni",
    "pagi ini",
    "this morning",
    "balik",
    "right now",
    "today",
    "now",
    "semalam",
    "another day",
]

TRANSPORT_SPECIFICITY_TERMS = [
    "station",
    "stesen",
    "platform",
    "laluan",
    "line",
    "rapidkl",
    "myrapidkl",
    "train",
    "tren",
    "interchange",
]

ISSUE_KEYWORDS = {
    "transport": {
        "incident": ["incident", "fire alarm", "help and rescue", "stuck", "tak boleh keluar", "not moving"],
        "technical_fault": [
            "technical fault",
            "technical issue",
            "brake failure",
            "brake failures",
            "faulty train component",
            "track switch failure",
            "gangguan sistem suis",
            "door malfunction",
            "door system malfunction",
            "suffered a technical fault",
        ],
        "delay": [
            "delay",
            "delays",
            "lambat",
            "kelewatan",
            "kesulitan",
            "next bas",
            "bus beroperasi",
            "having problems",
            "problem ke",
            "tak gerak",
            "tak gerak2",
            "tak bergerak",
            "gap masa",
            "berhenti lelama",
            "turun chan sow lin",
        ],
        "disruption": ["gangguan", "tidak stabil", "service update", "perkhidmatan"],
    },
    "telco_internet": {
        "outage": ["down", "outage", "no internet", "takde internet", "shutting off", "lost internet access"],
        "degradation": ["slow", "lambat", "pending", "resolve", "report already", "still nothing"],
        "login_failure": ["login", "session expired", "something is wrong", "not working"],
    },
    "gov_portals": {
        "login_failure": ["login", "session expired", "error", "failed", "cannot", "tak boleh"],
        "renewal": ["renew", "renewal", "roadtax", "permit"],
    },
    "banking_payments": {
        "transfer_failure": ["transfer", "transaction", "failed", "pending", "credited", "debit"],
        "login_failure": ["login", "locked", "cannot", "tak boleh", "app down"],
    },
    "flood_weather": {
        "flood": ["banjir", "flood", "jalan tutup", "road closure"],
    },
}


def detect_language_mix(text: str) -> str:
    low = text.lower()
    has_malay = any(token in low for token in ["tak", "boleh", "rosak", "lambat", "banjir", "tergendala", "sesak", "kelewatan", "kesulitan"])
    has_english = any(token in low for token in ["down", "issue", "error", "problem", "delay", "outage", "pending", "login", "transfer", "incident"])
    if has_malay and has_english:
        return "rojak"
    if has_malay:
        return "ms"
    if has_english:
        return "en"
    return "unknown"


def classify_category(text: str) -> str:
    low = text.lower()
    query_groups = load_yaml("queries.yaml").get("query_groups", {})
    for category, queries in query_groups.items():
        for query in queries:
            tokens = [
                token
                for token in query.lower().split()
                if (len(token) >= 4 or token in SHORT_ENTITY_TOKENS) and token not in GENERIC_QUERY_TOKENS
            ]
            for token in tokens:
                if re.search(r"\b" + re.escape(token) + r"\b", low):
                    return category
    return ""


def extract_entity(text: str, category: str = "") -> str:
    low = text.lower()
    if category == "transport":
        for canonical, aliases in TRANSPORT_ENTITY_ALIASES:
            if any(alias in low for alias in aliases):
                return canonical.title().replace("Sri Petaling", "Sri Petaling").replace("Kl Monorail", "KL Monorail")
    entities = load_yaml("entities.yaml").get("entities", {})
    groups = [category] if category else list(entities)
    for group in groups:
        for entity in sorted(entities.get(group, []), key=len, reverse=True):
            pattern = r"\b" + re.escape(entity.lower()) + r"\b"
            if re.search(pattern, low):
                return entity
    return ""


def extract_location(text: str) -> str:
    low = text.lower()
    sanitized = low
    for phrase in LINE_LOCATION_BLOCKERS:
        sanitized = sanitized.replace(phrase, " ")
    locations = [
        "mrt maluri",
        "pasar seni",
        "dang wangi",
        "kl gateway",
        "kepong baru",
        "semantan",
        "taman pertama",
        "bandar tasik selatan",
        "masjid jamek",
        "pudu",
        "cempaka",
        "kwasa",
        "muzium negara",
        "bangsar",
        "kl sentral",
        "maluri",
        "chan sow lin",
        "ara damansara",
        "kuala lumpur",
        "selangor",
        "johor",
        "penang",
        "kelantan",
        "ampang",
        "kelana jaya",
        "kl",
    ]
    label_map = {
        "kl": "Kuala Lumpur",
        "kl sentral": "KL Sentral",
        "kl gateway": "KL Gateway",
        "kelana jaya": "Kelana Jaya",
        "mrt maluri": "Maluri",
        "pasar seni": "Pasar Seni",
        "dang wangi": "Dang Wangi",
        "chan sow lin": "Chan Sow Lin",
        "ara damansara": "Ara Damansara",
        "kepong baru": "Kepong Baru",
        "semantan": "Semantan",
        "taman pertama": "Taman Pertama",
        "bandar tasik selatan": "Bandar Tasik Selatan",
        "masjid jamek": "Masjid Jamek",
        "muzium negara": "Muzium Negara",
    }
    for location in locations:
        pattern = r"\b" + re.escape(location) + r"\b"
        if re.search(pattern, sanitized):
            return label_map.get(location, location.title())
    return ""


def detect_severity(text: str) -> str:
    low = text.lower()
    if any(token in low for token in ["down", "outage", "banjir", "derailed", "cannot", "tak boleh", "incident", "fire alarm"]):
        return "high"
    if any(token in low for token in ["delay", "lambat", "pending", "issue", "problem", "kelewatan", "kesulitan"]):
        return "medium"
    return "low"


def is_complaint_signal(text: str) -> bool:
    low = text.lower()
    complaint_terms = [
        "complaint",
        "aduan",
        "down",
        "outage",
        "tak boleh",
        "rosak",
        "lambat",
        "delay",
        "pending",
        "gangguan",
        "problem",
        "issue",
        "error",
        "banjir",
        "takde internet",
        "tiada tindakan",
        "incident",
        "kelewatan",
        "kesulitan",
        "apologies for the inconvenience",
        "fire alarm",
    ]
    promo_terms = [
        "world cup",
        "watch all",
        "pas piala dunia",
        "get the latest service updates",
        "join the conversation",
        "for pelanggan",
        "official account",
        "focused on service updates and announcements",
    ]
    if any(term in low for term in promo_terms):
        return False
    return any(term in low for term in complaint_terms)


def transport_incident_signal_ok(text: str, entity_hint: str = "") -> bool:
    low = text.lower()

    blocked = CATEGORY_BLOCKED_TOKENS.get("transport", [])
    if any(token in low for token in blocked):
        return False

    strong_hit = any(token in low for token in TRANSPORT_STRONG_INCIDENT_TERMS)
    weak_hit = any(token in low for token in TRANSPORT_WEAK_INCIDENT_TERMS)
    live_context_hit = any(token in low for token in TRANSPORT_LIVE_CONTEXT_TERMS)

    entity = entity_hint or extract_entity(text, "transport")
    location = extract_location(text)
    specificity_hit = bool(
        entity
        or location
        or any(token in low for token in TRANSPORT_SPECIFICITY_TERMS)
    )

    if strong_hit and specificity_hit:
        return True
    if weak_hit and specificity_hit and live_context_hit:
        return True
    return False


def category_signal_ok(text: str, category: str, entity: str = "") -> bool:
    low = text.lower()
    blocked = CATEGORY_BLOCKED_TOKENS.get(category, [])
    blocked_hits = sum(token in low for token in blocked)
    if category in {"banking_payments", "gov_portals"} and blocked_hits >= 1:
        return False
    if category == "telco_internet" and blocked_hits >= 2:
        return False
    if category not in {"banking_payments", "gov_portals", "telco_internet"} and blocked_hits >= 2:
        return False

    required = CATEGORY_REQUIRED_TOKENS.get(category, [])
    if not required:
        return True

    if category == "banking_payments":
        incident_terms = [
            "pending",
            "error",
            "failed",
            "failure",
            "cannot",
            "tak boleh",
            "down",
            "outage",
            "transfer",
            "transaction",
            "login",
            "locked",
            "debit",
            "credited",
        ]
        return bool(entity and entity.lower() in low and any(token in low for token in incident_terms))

    if category == "gov_portals":
        portal_terms = [
            "portal",
            "app",
            "system",
            "login",
            "session expired",
            "unrecognized image",
            "renew",
            "renewal",
            "roadtax",
            "failed",
            "error",
            "down",
            "tak boleh",
            "cannot",
        ]
        return bool(entity and entity.lower() in low and any(token in low for token in portal_terms))

    if category == "telco_internet":
        service_terms = [
            "down",
            "outage",
            "no internet",
            "takde internet",
            "internet",
            "line",
            "signal",
            "network",
            "shutting off",
            "lost internet access",
            "coverage",
            "service",
            "broadband",
            "fiber",
            "resolve",
            "report already",
            "still nothing",
        ]
        onboarding_noise = [
            "facial verification",
            "face not valid",
            "cooldown timer",
            "unrecognized image",
            "ekyc",
            "id check",
            "business phone number",
            "clear the app data",
            "button press",
            "camera distortion",
            "photo of my face",
        ]
        if any(token in low for token in onboarding_noise) and not any(token in low for token in service_terms[:10]):
            return False
        return bool(entity and entity.lower() in low and any(token in low for token in service_terms))

    if category == "transport":
        return transport_incident_signal_ok(text, entity)

    if entity and entity.lower() in low and any(token in low for token in required):
        return True

    return any(token in low for token in required) and is_complaint_signal(low)


def extract_stub(text: str) -> dict[str, str]:
    category = classify_category(text)
    return {
        "category": category,
        "entity": extract_entity(text, category),
        "location": extract_location(text),
        "detected_language_mix": detect_language_mix(text),
        "severity": detect_severity(text),
    }


def extract_issue_key(text: str, category: str) -> str:
    low = text.lower()
    mapping = ISSUE_KEYWORDS.get(category, {})
    for issue_key, terms in mapping.items():
        if any(term in low for term in terms):
            return issue_key
    return ""
