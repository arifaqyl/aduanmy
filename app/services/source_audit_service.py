SOURCE_AUDIT_TEMPLATE = {
    "threads": {
        "primary_method": "public scrape against public profiles/posts/hashtags",
        "fallback_method": "logged-in browser profile collection",
        "failure_modes": [
            "dynamic rendering limits collection depth",
            "public visibility may be capped without login",
            "markup drift can break parsers quickly",
        ],
    },
    "reddit": {
        "primary_method": "public endpoint or public HTML collection",
        "fallback_method": "OAuth or maintained scraper workflow",
        "failure_modes": [
            "public endpoint behavior can drift to 403s",
            "search quality may vary by route",
            "comment depth can be expensive",
        ],
    },
    "x": {
        "primary_method": "session-backed twitter-cli search/feed export",
        "fallback_method": "cookie refresh or browser-assisted path",
        "failure_modes": [
            "session expiry",
            "login gates",
            "platform UI/search changes outside CLI expectations",
        ],
    },
    "official": {
        "primary_method": "official pages plus open data grounding; GTFS-R is usable for vehicle positions but not yet for Rapid Rail alert truth",
        "fallback_method": "generic crawl and content extraction when official pages are fetchable",
        "failure_modes": [
            "page layout drift",
            "anti-bot protection on MyRapid pages",
            "GTFS-R still lacks stable Rapid Rail service-alert/trip-update coverage",
            "limited historical depth on official sites",
            "inconsistent update cadence",
        ],
    },
}
