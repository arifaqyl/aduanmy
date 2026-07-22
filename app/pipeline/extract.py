from __future__ import annotations

import re

from app.core.files import load_yaml
from app.core.malaysia_transport_scope import has_strict_malaysia_transport_anchor
from app.pipeline.geo import extract_location as _geo_extract_location

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
    ("seremban line", ["ktm seremban", "seremban line", "komuter seremban"]),
    ("port klang line", ["ktm port klang", "port klang line", "komuter port klang"]),
    ("skudai line", ["ktm skudai", "skudai line", "komuter skudai"]),
    ("butterworth-padang besar", ["butterworth padang besar", "ktm butterworth", "ets butterworth"]),
    ("east coast line", ["east coast rail link", "ecrl", "laluan pantai timur"]),
    ("penang rapid", ["rapid penang", "bas penang", "penang rapid"]),
    ("rts link", ["rts link", "rts johor", "rapid transit system johor"]),
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
        "replying to",
        "pov:",
        "pov ",
        "jom jalan",
        "jalan-jalan",
        "every single time",
        "when i don't have",
        "goodbye to astro",
        "people are saying goodbye",
        "running to",
        "intern at",
        "internship at",
        "connected with lrt",
        "dekat lrt",
        "near lrt station",
        "walking distance to lrt",
        "below market",
        "pas piala dunia",
        "world cup",
        "hot meals",
        "bayangkan",
        "can expect",
        "may experience",
        "what if",
        "akan jd",
        "akan jadi",
        "serve really good",
        "delay their opening",
        "opening delayed",
        "delay the opening",
        "under construction",
        "construction progress",
        "launch date",
        "commence operations",
        "start operations",
        "free rides",
        "free ride",
        "preview ride",
        "preview rides",
        "percuma sehingga",
        "percuma hingga",
        "naik percuma",
        "rides until",
        "rides till",
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
    "tak bukak pintu",
    "pintu tak buka",
    "tak buka pintu",
    "buat hal",
    "jerking",
    "stop lama",
    "berhenti lama",
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

# Speculation / future scenario — not a current disruption (e.g. "Bayangkan LRT3… akan jd macam Pasar Seni").
TRANSPORT_HYPOTHETICAL_TERMS = [
    "bayangkan",
    "imagin",
    "what if",
    "what would",
    "kalau nanti",
    "nanti bila",
    "bila nanti",
    "akan jadi",
    "akan jd",
    "akan menjadi",
    "will become",
    "will be like",
    "going to be like",
    "might become",
    "could become",
    "worst case",
]

# General non-live patterns — any line/mode, not one-off phrase lists per project.
TRANSPORT_SARCASTIC_WAIT_RE = re.compile(r"\b(?:ko\s+)?tunggu\s+je(?:\s+la)?\b", re.I)
TRANSPORT_FUTURE_INCIDENT_RE = re.compile(
    r"\b(?:akan|nanti|will|going\s+to|expected|might|could|mula|cepat).{0,36}"
    r"\b(?:problem|rosak|delay|delays|delayed|lambat|gangguan|breakdown|issue|issues)\b"
    r"|\b(?:problem|rosak|delay|lambat|gangguan).{0,24}\b(?:nanti|lepas|mcm|macam|like)\b",
    re.I,
)
TRANSPORT_FUTURE_WAIT_RE = re.compile(
    r"\b(?:makin\s+lama|akan|expected|nanti).{0,40}\b(?:tunggu|menunggu)\b",
    re.I,
)
TRANSPORT_PLANNING_DEBATE_RE = re.compile(
    r"\b(?:downscope|downgrade|cost\s+cutting|kos\s+penjimatan|kecikkan|potong\s+jadi|"
    r"\d+\s*koc|koc\s+tren|gerabak|billiun|billion|projek\s+ni|pembinaan|keputusan\s+bodoh|"
    r"penjimatan|first\s+week|kapasiti|kekerapan\s+tren|tak\s+amik\s+pengajaran)\b",
    re.I,
)
TRANSPORT_CONDITIONAL_LINE_RE = re.compile(
    r"\b(?:if|when|bila|kalau)\s+(?:the\s+)?(?:lrt|mrt|ktm|monorail|komuter|ets|line|tren|bas|bus)\b",
    re.I,
)
TRANSPORT_THREADS_TIME_CHROME_RE = re.compile(
    r"(?:^|\s)[a-z0-9_\.]{3,24}\s+\d{1,2}[hm]\b",
    re.I,
)
# Journalistic / operator-advisory third person — not a rider on the train now.
TRANSPORT_NEWS_VOICE_RE = re.compile(
    r"\b(?:commuters?\s+(?:can|may|are|were|have)\s+(?:expect|experience|advised|facing|been)|"
    r"passengers?\s+(?:are|were|have\s+been)\s+(?:advised|facing|experiencing)|"
    r"motorists?\s+(?:are|were)\s+advised|"
    r"according\s+to\s+(?:rapid\s*kl|prasarana|ktmb?|myrapid|officials?)|"
    r"authorities?\s+(?:said|say|have\s+said)|"
    r"(?:service|train\s+service)\s+(?:has\s+been|was)\s+(?:disrupted|suspended|delayed)|"
    r"commuters\s+can\s+expect|"
    r"allow\s+(?:for\s+)?extra\s+time)\b",
    re.I,
)
TRANSPORT_SCHEDULE_TRIVIA_RE = re.compile(
    r"\b(?:operating\s+hours|waktu\s+operasi|first\s+train|last\s+train|"
    r"jadual\s+(?:waktu|tren)|timetable\s+only|headway\s+is)\b",
    re.I,
)
TRANSPORT_RIDER_WAITING_RE = re.compile(
    r"\b(?:kena\s+tunggu|tunggu\s+(?:lama|dekat|lagi|tren|bas|train|platform|stesen|station)|"
    r"menunggu\s+(?:tren|bas|train|dekat|platform|stesen|station)|"
    r"waiting\s+(?:for|at|on)|waited\s+\d+)\b",
    re.I,
)

# Forward-looking advisory copy without proof of an ongoing incident.
TRANSPORT_ADVISORY_TERMS = [
    "can expect",
    "may experience",
    "might experience",
    "expected to",
    "is expected",
    "are expected",
    "please plan",
    "plan extra time",
    "allow extra time",
    "commuters are advised",
    "advised to plan",
]

TRANSPORT_QUIET_OR_SPECULATIVE_PATTERNS = [
    r"\btak\s+(?:padat|sesak|ramai)\b",
    r"\b(?:delay|problem|gangguan|rosak)\s+(?:ke|tak)(?:\s+\w+){0,2}\s*\?",
    r"\bsebab\s+takut\s+(?:train|tren).{0,30}\b(?:problem|delay|gangguan)\b",
]

# Present / ongoing incident — required when text is advisory, weak, or hypothetical-adjacent.
TRANSPORT_PRESENT_ACTIVE_TERMS = [
    "stuck",
    "stucked",
    "tak gerak",
    "tak gerak2",
    "tak bergerak",
    "kenape tak gerak",
    "kenapa pulak ni",
    "right now",
    "currently",
    "sedang",
    "sekarang",
    "skrg",
    "hari ni",
    "harini",
    "pagi ni",
    "pagi ini",
    "this morning",
    "today",
    "now",
    "tadi",
    "baru ni",
    "semalam",
    "again",
    "still",
    "experiencing",
    "is delayed",
    "are delayed",
    "was delayed",
    "has been delayed",
    "have been delayed",
    "kena tunggu",
    "waiting for",
    "not moving",
    "tak boleh keluar",
    "disembark",
    "manual operation",
    "manually operated",
    "fire alarm",
    "emergency brake",
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
    "still",
    "again",
    "sekarang",
    "skrg",
    "tadi",
    "baru ni",
    "ke?",
]

TRANSPORT_SPECIFICITY_TERMS = [
    "station",
    "stesen",
    "platform",
    "laluan",
    "rapidkl",
    "myrapidkl",
    "train",
    "tren",
    "interchange",
]

TRANSPORT_ACTIONABLE_IMPACT_TERMS = [
    "waiting",
    "waited",
    "kena tunggu",
    "queue",
    "beratur",
    "not moving",
    "tak gerak",
    "tak bergerak",
    "cannot board",
    "tak boleh naik",
    "cannot exit",
    "tak boleh keluar",
    "stranded",
    "terkandas",
    "missed",
    "late for",
    "terlambat",
    "jadi lambat",
    "sampai lambat",
    "lambat ke opis",
    "penuh",
    "sesak",
    "packed",
    "evacuated",
    "ditutup",
    "closed",
    "no train",
    "tiada tren",
    "pintu tak bukak",
    "tak bukak pintu",
    "pintu tak buka",
    "tak buka pintu",
    "stop lama",
    "berhenti lama",
    "ramai manusia",
    "door malfunction",
    "shuttle bus",
    "bas perantara",
]

TRANSPORT_CONCRETE_CAUSE_TERMS = [
    "due to",
    "disebabkan",
    "technical fault",
    "technical issue",
    "fire alarm",
    "emergency brake",
    "brake failure",
    "track switch",
    "signal failure",
    "power failure",
    "door malfunction",
    "manual operation",
]

TRANSPORT_CHATTER_PATTERNS = [
    r"\b(?:what do you think|thoughts|korang rasa|siapa setuju|unpopular opinion)\b",
    r"\b(?:throwback|remember when|dulu|tahun lepas|last year)\b",
    r"\b(?:always|selalu|hari2|every day)\b.{0,50}\b(?:delay|lambat|problem|rosak)\b",
    r"\b(?:i think|rasanya|rasa macam)\b.{0,60}\b(?:delay|problem|gangguan)\b",
]

# Infrastructure planning / budget debate — not a live rider report.
TRANSPORT_PLANNING_OPINION_TERMS = [
    "kenselkan",
    "kecikkan saiz",
    "gerabak",
    "potong jadi",
    "plan asal",
    "bukan jimat",
    "claim jimat",
    "billiun",
    "billion",
    "downgrade",
    "tanpa downgrade",
    "zaman bn",
    "cost cutting",
    "pembinaan",
    "projek ni",
]

# General “LRT is useless / too small” opinion — not an active incident today.
TRANSPORT_USELESS_OPINION_TERMS = [
    "apa faedah",
    "x function",
    "rumah sebelah lrt",
    "rumah sebelah",
    "terpaling terdesak",
    "kecik sangat",
    "sama size dgn",
    "sama size dengan",
    "cuma yg",
    "how long do we have to cope",
    "not recommend naik",
]

# Rider must signal they mean *today* (or a fresh relative time like “10h” on Threads).
TRANSPORT_TODAY_RIDER_TERMS = [
    "hari ni",
    "harini",
    "pagi ni",
    "pagi ini",
    "this morning",
    "today",
    "now",
    "right now",
    "currently",
    "sekarang",
    "skrg",
    "baru ni",
]


def _contains_transport_marker(low: str, token: str) -> bool:
    if re.fullmatch(r"[a-z0-9]+", token):
        # Also guard against underscores — social handles like "ktm_switzerland"
        # or "mrt_bangkok" would otherwise read as a bare "ktm"/"mrt" mention.
        return bool(re.search(r"(?<![a-z0-9_])" + re.escape(token) + r"(?![a-z0-9_])", low))
    return token in low


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


def extract_bus_route(text: str) -> str:
    try:
        from app.db.gtfs_store import all_short_names

        catalog = all_short_names()
    except Exception:
        catalog = set()
    # Bare numbers are commonly dates, durations, engagement counts, dosages
    # or train times. Only accept a numeric bus route with an explicit route
    # marker so "(250 pax)" or "500 micrograms" don't get misread as a route.
    candidates: list[str] = []
    for match in re.finditer(r"\b(?:route|bus|bas|laluan)\s*#?\s*(T?\d{2,3})\b", text, re.I):
        candidates.append(match.group(1).upper())
    for match in re.finditer(r"\b(T\d{2,3})\b", text, re.I):
        candidates.append(match.group(1).upper())
    if not catalog:
        return candidates[0] if candidates else ""
    for candidate in candidates:
        for form in (candidate, candidate.removeprefix("T"), f"T{candidate.removeprefix('T')}"):
            if form in catalog:
                return form
    low = text.lower()
    route_context = re.compile(r"\b(?:route|bus|bas|laluan|no\.?|nombor|#)\b", re.I)
    for name in sorted(catalog, key=len, reverse=True):
        if len(name) < 3:
            continue
        for occurrence in re.finditer(r"\b" + re.escape(name.lower()) + r"\b", low):
            if not name.isdigit():
                return name
            # Purely numeric route names ("250", "780") are too easy to
            # collide with unrelated quantities — require nearby route wording.
            window = low[max(0, occurrence.start() - 20) : occurrence.start()]
            if route_context.search(window):
                return name
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
    sanitized = text.lower()
    for phrase in LINE_LOCATION_BLOCKERS:
        sanitized = sanitized.replace(phrase, " ")
    return _geo_extract_location(sanitized)


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


TRANSPORT_LINE_INFO_TERMS = [
    "km route",
    "km long",
    "kilometer",
    "kilometre",
    "stations",
    "stesen",
    "interchange",
    "persimpangan",
    "end-to-end",
    "journey time",
    "max speed",
    "km/h",
    "capacity",
    "penumpang",
    "three-car",
    "underground",
    "bawah tanah",
    "car trains",
]


def transport_line_info_signal_ok(text: str, entity_hint: str = "") -> bool:
    """Informational route-fact posts — not live disruptions."""
    low = text.lower()
    mentions_line = any(
        token in low
        for token in [
            "lrt",
            "mrt",
            "ktm",
            "monorail",
            "line",
            "laluan",
            "lrt3",
            "kelana",
            "ampang",
            "kajang",
            "putrajaya",
            "shah alam",
            "komuter",
            "ets",
            "transit",
        ]
    )
    launch_keywords = [
        "launch", "open", "free ride", "start operation", "commence", "first day",
        "preview", "review", "opening", "launched", "opened", "starts operation"
    ]
    is_launch_or_review = mentions_line and any(kw in low for kw in launch_keywords)

    spam_and_future_blockers = [
        "for sale", "for rent", "asking price", "below market", "investment",
        "berminat boleh pm", "dm for viewing", "walkable walking distance",
        "walking distance", "corner lot", "apartment", "condo", "internship",
        "hiring", "fresh graduate", "salary:", "jobstreet",
        "delay their opening", "opening delayed", "delay the opening",
        "under construction", "construction progress", "launch date"
    ]
    if any(token in low for token in spam_and_future_blockers):
        return False

    promo_block = [
        "free rides",
        "free ride",
        "preview ride",
        "preview rides",
        "percuma sehingga",
        "naik percuma",
        "world cup",
        "pas piala dunia",
    ]
    if not is_launch_or_review and any(term in low for term in promo_block):
        return False
    if is_launch_or_review:
        return True
    if transport_incident_signal_ok(text, entity_hint):
        return False
    info_hits = sum(1 for term in TRANSPORT_LINE_INFO_TERMS if term in low)
    has_numbers = bool(re.search(r"\d+(\.\d+)?\s*(km|stesen|stations|min)", low))
    return mentions_line and (info_hits >= 2 or has_numbers)


def _transport_direct_experience_hit(low: str) -> bool:
    if _transport_rider_waiting_hit(low):
        return True
    return any(
        token in low
        for token in [
            "stuck",
            "tak gerak",
            "tak bergerak",
            "waiting for",
            "is delayed",
            "was delayed",
            "still delayed",
            "fire alarm",
            "emergency",
            "pintu tak bukak",
            "tak bukak pintu",
            "pintu tak buka",
            "tak buka pintu",
            "not moving",
            "manual operation",
            "stop lama",
            "berhenti lama",
            "cannot board",
            "tak boleh naik",
            "tak boleh keluar",
        ]
    )


def _transport_rider_waiting_hit(low: str) -> bool:
    if TRANSPORT_SARCASTIC_WAIT_RE.search(low):
        return False
    if TRANSPORT_FUTURE_WAIT_RE.search(low):
        return False
    return bool(TRANSPORT_RIDER_WAITING_RE.search(low))


def _transport_present_active_hit(low: str) -> bool:
    if any(token in low for token in TRANSPORT_PRESENT_ACTIVE_TERMS):
        return True
    return _transport_rider_waiting_hit(low)


def _transport_actionable_impact_hit(low: str) -> bool:
    if any(token in low for token in TRANSPORT_ACTIONABLE_IMPACT_TERMS):
        return True
    return _transport_rider_waiting_hit(low)


def transport_non_live_opinion(text: str) -> bool:
    """Reject prediction, planning debate, sarcasm — applies to all lines/modes."""
    low = (text or "").lower()
    if TRANSPORT_SARCASTIC_WAIT_RE.search(low):
        return True
    if TRANSPORT_FUTURE_INCIDENT_RE.search(low):
        return True
    if TRANSPORT_FUTURE_WAIT_RE.search(low):
        return True
    if TRANSPORT_PLANNING_DEBATE_RE.search(low):
        return True
    if TRANSPORT_CONDITIONAL_LINE_RE.search(low):
        return True
    if any(term in low for term in TRANSPORT_PLANNING_OPINION_TERMS):
        return True
    if any(term in low for term in TRANSPORT_USELESS_OPINION_TERMS):
        return True
    # News/advisory voice without first-person rider evidence is not Live today.
    if TRANSPORT_NEWS_VOICE_RE.search(low) and not _transport_direct_experience_hit(low):
        return True
    if TRANSPORT_SCHEDULE_TRIVIA_RE.search(low) and not (
        _transport_actionable_impact_hit(low) or _transport_direct_experience_hit(low)
    ):
        return True
    return False


def transport_predictive_opinion(text: str) -> bool:
    """Backward-compatible alias for non-live opinion detection."""
    return transport_non_live_opinion(text)


def transport_incident_signal_ok(text: str, entity_hint: str = "") -> bool:
    low = text.lower()
    if transport_non_live_opinion(text):
        return False
    # Word-boundary matching matters here: short tokens like "line" and "ets"
    # are common substrings of unrelated English words ("adrenaline", "tickets",
    # "streets", "assets"...). A naive `token in low` check turned those into
    # false transit mentions and let non-transport posts through.
    unambiguous_transit_hit = any(
        _contains_transport_marker(low, token)
        for token in [
            "lrt",
            "mrt",
            "ktm",
            "monorail",
            "line",
            "laluan",
            "lrt3",
            "komuter",
            "ets",
            "transit",
            "train",
            "tren",
            "bas",
            "bus",
        ]
    )
    # These are also real Malaysian place/district names ("Putrajaya",
    # "Kajang") — a bare mention shows up in food ads, job posts, and local
    # chatter with zero transit relevance. Only count them when paired with
    # an explicit line/mode word, or written as an actual line name.
    ambiguous_place_hit = any(
        _contains_transport_marker(low, token)
        for token in ["kelana", "ampang", "kajang", "putrajaya", "shah alam"]
    ) and (
        unambiguous_transit_hit
        or bool(
            re.search(
                r"\b(?:kelana jaya|ampang|kajang|putrajaya|shah alam)\s+line\b"
                r"|\bline\s+(?:kelana jaya|ampang|kajang|putrajaya|shah alam)\b",
                low,
            )
        )
    )
    mentions_line = unambiguous_transit_hit or ambiguous_place_hit
    launch_keywords = [
        "launch", "open", "free ride", "start operation", "commence", "first day",
        "preview", "review", "opening", "launched", "opened", "starts operation"
    ]
    is_launch_or_review = mentions_line and any(kw in low for kw in launch_keywords)

    blocked = CATEGORY_BLOCKED_TOKENS.get("transport", [])
    if is_launch_or_review:
        spam_blockers = [
            "for sale", "for rent", "asking price", "below market", "investment",
            "berminat boleh pm", "dm for viewing", "walkable walking distance",
            "walking distance", "corner lot", "apartment", "condo", "internship",
            "hiring", "fresh graduate", "salary:", "jobstreet",
            "delay their opening", "opening delayed", "delay the opening",
            "under construction", "construction progress", "launch date"
        ]
        if any(token in low for token in spam_blockers):
            return False
    else:
        if any(token in low for token in blocked):
            return False

    hypothetical_hit = any(token in low for token in TRANSPORT_HYPOTHETICAL_TERMS)
    advisory_hit = any(token in low for token in TRANSPORT_ADVISORY_TERMS)
    present_active_hit = _transport_present_active_hit(low)
    speculative_question_hit = any(
        re.search(pattern, low, re.I) for pattern in TRANSPORT_QUIET_OR_SPECULATIVE_PATTERNS
    )

    # Casual LRT/MRT mention without an active problem — e.g. "condo near LRT".
    mentions_transit = any(
        token in low
        for token in ["lrt", "mrt", "ktm", "rapidkl", "rapid kl", "komuter", "bas rapid"]
    )
    strong_hit = any(token in low for token in TRANSPORT_STRONG_INCIDENT_TERMS)
    weak_hit = any(token in low for token in TRANSPORT_WEAK_INCIDENT_TERMS)
    live_context_hit = any(token in low for token in TRANSPORT_LIVE_CONTEXT_TERMS)
    direct_experience_hit = _transport_direct_experience_hit(low)
    measured_hit = bool(
        re.search(r"\b\d{1,3}\s*(?:min|mins|minute|minutes|minit|jam|hour|hours)\b", low)
    )

    entity = entity_hint or extract_entity(text, "transport")
    # A Malaysian place/state name alone is not enough — "Selangor" or
    # "Petaling Jaya" show up in food ads, job posts, and unrelated chatter.
    # Require an actual transit anchor (line/mode mention, named entity, or a
    # transit-specific noun like "station"/"platform") before it counts.
    specificity_hit = bool(
        mentions_line
        or entity
        or any(_contains_transport_marker(low, token) for token in TRANSPORT_SPECIFICITY_TERMS)
    )

    if not specificity_hit:
        return False

    # Questions and quiet-service observations are discovery chatter, not evidence.
    if speculative_question_hit and not direct_experience_hit:
        return False

    # Future/hypothetical posts — e.g. "Bayangkan LRT3 start… Glenmarie akan jd macam Pasar Seni?"
    if hypothetical_hit and not present_active_hit:
        return False

    # Advisory headlines without ongoing live wording — e.g. "Commuters can expect delays."
    if advisory_hit and not present_active_hit and not live_context_hit:
        return False

    # Weak "problem/delay" inside a conditional future chain still isn't a live incident.
    if hypothetical_hit:
        return False

    if any(token in low for token in TRANSPORT_PLANNING_OPINION_TERMS):
        return False

    # Must describe something going wrong now — not just name-drop a line or station.
    if strong_hit and (present_active_hit or live_context_hit or not advisory_hit):
        return True
    if weak_hit and direct_experience_hit:
        return True
    if weak_hit and measured_hit and (present_active_hit or live_context_hit):
        return True
    if weak_hit and mentions_transit and any(token in low for token in ["tak gerak", "rosak", "lambat", "delay", "gangguan"]):
        if direct_experience_hit or measured_hit:
            return True
    return False


def transport_rider_signal_worthwhile(text: str, entity_hint: str = "") -> bool:
    """Strict Threads gate: keep observable live conditions, reject discussion-only posts."""
    if transport_non_live_opinion(text):
        return False
    if not transport_incident_signal_ok(text, entity_hint):
        return False

    low = text.lower()
    entity = entity_hint or extract_entity(text, "transport")
    location = extract_location(text)
    if not has_strict_malaysia_transport_anchor(text, entity=entity, location=location):
        return False

    chatter_hit = any(re.search(pattern, low, re.I) for pattern in TRANSPORT_CHATTER_PATTERNS)
    present_hit = _transport_present_active_hit(low)
    live_context_hit = any(token in low for token in TRANSPORT_LIVE_CONTEXT_TERMS)
    impact_hit = _transport_actionable_impact_hit(low)
    cause_hit = any(token in low for token in TRANSPORT_CONCRETE_CAUSE_TERMS)
    measured_hit = bool(
        re.search(r"\b\d{1,3}\s*(?:min|mins|minute|minutes|minit|jam|hour|hours)\b", low)
    )
    direct_hit = _transport_direct_experience_hit(low)

    observable_hit = impact_hit or cause_hit or measured_hit or direct_hit
    riding_delay_hit = any(
        token in low for token in ["delay", "delays", "delayed", "kelewatan", "gangguan", "lambat", "disruption"]
    ) and present_hit
    incident_now_hit = any(token in low for token in ["incident", "gangguan", "disruption"]) and present_hit
    if riding_delay_hit or incident_now_hit:
        observable_hit = True

    # Politics, housing, or infrastructure hypotheticals — never a live rider signal.
    if any(
        token in low
        for token in [
            "rasuah",
            "corruption",
            "ptptn",
            "rm277",
            "enough to build",
            "enough to clear",
            "my selangorku",
            "harga rumah",
            "nak beli rumah",
            "mampu buat",
            "minute tunggu grab",
            "tunggu grab",
            "years in development",
            "was delayed multiple times",
            "better mrt or lrt laju",
            "timing sgt lambat ye, better",
        ]
    ):
        return False

    if any(token in low for token in TRANSPORT_PLANNING_OPINION_TERMS):
        return False

    # Habitual gripe without a today signal ("dah lambat", "selalu sesak").
    if re.search(r"\b(?:dah lambat|sesak penuh|selalu)\b", low) and not (
        present_hit or measured_hit or direct_hit or riding_delay_hit
    ):
        return False

    # Crowding / generic “sesak” alone is not enough — need a live rider cue today.
    if (
        impact_hit
        and not (direct_hit or measured_hit or riding_delay_hit or cause_hit)
        and not transport_rider_today_context_ok(text)
    ):
        return False

    # A concrete cause or measured/direct evidence is itself proof of a live incident —
    # only fall back to requiring an explicit "today" cue for weaker, cause-less reports.
    if not (cause_hit or direct_hit or measured_hit) and not transport_rider_today_context_ok(text):
        return False

    # Aggregated Threads search previews (multiple handles + relative timestamps).
    if len(re.findall(r"\b[a-z0-9_\.]{3,24}\s+\d+[hm]\b", low)) >= 2 and not (direct_hit or measured_hit):
        return False

    if chatter_hit and not (present_hit and observable_hit):
        return False
    if "?" in low and not observable_hit:
        return False
    return observable_hit


def transport_rider_today_context_ok(text: str) -> bool:
    """True when the post reads like a same-day rider experience (not evergreen opinion)."""
    low = text.lower()
    if any(token in low for token in TRANSPORT_TODAY_RIDER_TERMS):
        return True
    if re.search(r"\b\d{1,3}\s*(?:min|mins|minute|minutes|minit|jam|hour|hours)\b", low):
        return True

    direct_hit = _transport_direct_experience_hit(low)
    if direct_hit:
        return True

    # Threads handle + relative time ("user20h") is scrape chrome, not rider evidence.
    if TRANSPORT_THREADS_TIME_CHROME_RE.search(low):
        return False

    # Bare "14h"/"20h" without direct experience is not a live rider cue.
    if re.search(r"\b\d{1,2}[hm]\b", low):
        return bool(
            any(token in low for token in ["tadi", "baru ni", "sekarang", "skrg", "pagi ni", "this morning"])
        )
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
            "port in",
            "porting",
            "number transfer",
            "mnp",
            "sim registration",
            "sim activation",
            "new sim",
            "esim",
            "wrong bill",
            "overcharged",
            "bill dispute",
            "plan price",
            "postpaid plan",
            "prepaid plan",
            "contract renewal",
            "early termination",
            "upgrade plan",
            "change plan",
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
