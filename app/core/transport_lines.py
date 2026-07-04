from __future__ import annotations

import re


def _token_hit(token: str, blob: str) -> bool:
    """Word-boundary token check — plain substring matching lets short line
    codes like "ktm" false-positive inside unrelated handles/compounds
    (e.g. "ktm_switzerland")."""
    if " " in token:
        return token in blob
    return re.search(r"(?<![a-z0-9_])" + re.escape(token) + r"(?![a-z0-9_])", blob) is not None


# Operational services shown on the live status board. Static service details are
# context only; users should follow the operator timetable link before travelling.
LINE_CATALOG: list[dict] = [
    {
        "id": "lrt3",
        "name": "LRT Shah Alam Line",
        "mode": "rail",
        "operator": "Rapid KL",
        "region": "Petaling Jaya, Shah Alam and Klang",
        "route": "Bandar Utama to Johan Setia",
        "service_hours": "Passenger service starts at 06:00 on 29 June 2026",
        "peak_frequency": "Check Rapid KL after passenger operations begin",
        "timetable_url": "https://myrapid.com.my/rail/routes",
        "service_start_date": "2026-06-29",
        "match": ["lrt3", "lrt 3", "shah alam line", "lrt shah alam", "laluan shah alam"],
    },
    {
        "id": "kelana-jaya",
        "name": "Kelana Jaya Line",
        "mode": "rail",
        "operator": "Rapid KL",
        "region": "Klang Valley",
        "route": "Gombak to Putra Heights",
        "service_hours": "From 06:00 daily; last trains vary by station",
        "peak_frequency": "About every 3 minutes on weekdays",
        "timetable_url": "https://myrapid.com.my/bus-train/rapid-kl/lrt/",
        "match": ["kelana jaya", "lrt kelana", "laluan kelana"],
    },
    {
        "id": "ampang-sri-petaling",
        "name": "Ampang / Sri Petaling Lines",
        "mode": "rail",
        "operator": "Rapid KL",
        "region": "Klang Valley",
        "route": "Ampang or Putra Heights to Sentul Timur",
        "service_hours": "From 06:00 daily; last trains vary by station",
        "peak_frequency": "About every 6 minutes on each branch",
        "timetable_url": "https://myrapid.com.my/bus-train/rapid-kl/lrt/",
        "match": ["laluan ampang", "ampang line", "sri petaling", "laluan sri petaling"],
    },
    {
        "id": "kajang",
        "name": "MRT Kajang Line",
        "mode": "rail",
        "operator": "Rapid KL",
        "region": "Klang Valley",
        "route": "Kwasa Damansara to Kajang",
        "service_hours": "About 06:00 to midnight daily",
        "peak_frequency": "About every 4 minutes on weekdays",
        "timetable_url": "https://myrapid.com.my/bus-train/rapid-kl/mrt-kajang/",
        "match": ["kajang line", "mrt kajang", "laluan kajang"],
    },
    {
        "id": "putrajaya",
        "name": "MRT Putrajaya Line",
        "mode": "rail",
        "operator": "Rapid KL",
        "region": "Klang Valley",
        "route": "Kwasa Damansara to Putrajaya Sentral",
        "service_hours": "About 06:00 to midnight daily",
        "peak_frequency": "About every 5 minutes on weekdays",
        "timetable_url": "https://myrapid.com.my/bus-train/rapid-kl/mrt-putrajaya/",
        "match": ["putrajaya line", "mrt putrajaya", "laluan putrajaya"],
    },
    {
        "id": "kajang-putrajaya",
        "name": "Kajang / Putrajaya MRT",
        "mode": "rail",
        "operator": "Rapid KL",
        "region": "Klang Valley",
        "route": "Reports affecting both MRT lines",
        "service_hours": "About 06:00 to midnight daily",
        "peak_frequency": "Line-dependent",
        "timetable_url": "https://myrapid.com.my/bus-train/rapid-kl/",
        "match": ["kajang/putrajaya lines", "kajang and putrajaya", "putrajaya and kajang"],
    },
    {
        "id": "monorail",
        "name": "KL Monorail",
        "mode": "rail",
        "operator": "Rapid KL",
        "region": "Kuala Lumpur",
        "route": "KL Sentral to Titiwangsa",
        "service_hours": "About 06:00 to midnight daily",
        "peak_frequency": "About every 6 minutes on weekdays",
        "timetable_url": "https://myrapid.com.my/bus-train/rapid-kl/monorail/",
        "match": ["monorail", "kl monorail", "monorel"],
    },
    {
        "id": "brt-sunway",
        "name": "BRT Sunway Line",
        "mode": "bus",
        "operator": "Rapid KL",
        "region": "Selangor",
        "route": "Sunway-Setia Jaya to USJ 7",
        "service_hours": "About 06:00 to midnight daily",
        "peak_frequency": "About every 6 minutes",
        "timetable_url": "https://myrapid.com.my/bus-train/rapid-kl/brt/",
        "match": ["brt sunway", "sunway line", "sunway-setia jaya"],
    },
    {
        "id": "ktm-komuter",
        "name": "KTM Komuter Klang Valley",
        "mode": "rail",
        "operator": "KTMB",
        "region": "Klang Valley and Negeri Sembilan",
        "route": "Batu Caves to Pulau Sebang; Tanjung Malim to Port Klang",
        "service_hours": "Fixed timetable; varies by station and day",
        "peak_frequency": "Use the dated KTMB timetable",
        "timetable_url": "https://www.ktmb.com.my/traintime.html",
        "match": ["ktm", "ktmb", "komuter", "seremban line", "port klang line"],
    },
    {
        "id": "ktm-north",
        "name": "KTM Komuter Utara",
        "mode": "rail",
        "operator": "KTMB",
        "region": "Perlis, Kedah, Penang and Perak",
        "route": "Padang Besar to Butterworth and Padang Rengas",
        "service_hours": "Fixed timetable",
        "peak_frequency": "Use the dated KTMB timetable",
        "timetable_url": "https://www.ktmb.com.my/traintime.html",
        "match": ["komuter utara", "ktm utara", "padang besar butterworth"],
    },
    {
        "id": "ets-intercity",
        "name": "KTM ETS / Intercity",
        "mode": "rail",
        "operator": "KTMB",
        "region": "Peninsular Malaysia",
        "route": "West Coast ETS and East/South Intercity network",
        "service_hours": "Reservation-based fixed timetable",
        "peak_frequency": "Use the dated KTMB timetable",
        "timetable_url": "https://www.ktmb.com.my/traintime.html",
        "match": ["ets", "intercity", "shuttle tebrau", "east coast line"],
    },
    {
        "id": "klia-rail",
        "name": "KLIA Ekspres / Transit",
        "mode": "rail",
        "operator": "Express Rail Link",
        "region": "Kuala Lumpur, Putrajaya and Sepang",
        "route": "KL Sentral to KLIA Terminal 1 and Terminal 2",
        "service_hours": "First departures about 05:00; final arrivals after midnight",
        "peak_frequency": "15 minutes peak; 30 minutes off-peak/weekends",
        "timetable_url": "https://www.kliaekspres.com/products-fares/klia-transit/",
        "match": ["klia ekspres", "klia express", "klia transit", "erl"],
    },
    {
        "id": "sabah-railway",
        "name": "Sabah State Railway",
        "mode": "rail",
        "operator": "JKNS",
        "region": "Sabah",
        "route": "Tanjung Aru to Beaufort and Tenom",
        "service_hours": "Limited fixed timetable; confirm with JKNS",
        "peak_frequency": "Not a turn-up-and-go service",
        "timetable_url": "https://www.sabahrailway.my/",
        "match": ["sabah state railway", "keretapi negeri sabah", "tanjung aru tenom", "beaufort tenom"],
    },
    {
        "id": "rapid-bus",
        "name": "Rapid KL Bus",
        "mode": "bus",
        "operator": "Rapid Bus",
        "region": "Klang Valley",
        "route": "Stage, feeder and selected local bus routes",
        "service_hours": "Most routes start around 06:00; last buses vary",
        "peak_frequency": "Route-dependent; commonly 15-20 minutes",
        "timetable_url": "https://myrapid.com.my/bus-train/rapid-kl/bus/",
        "match": ["rapid kl bus", "bas rapid", "rapidkl bus", "route "],
    },
    {
        "id": "penang",
        "name": "Rapid Penang",
        "mode": "bus",
        "operator": "Rapid Bus",
        "region": "Penang and nearby corridors",
        "route": "Island and Seberang Perai routes",
        "service_hours": "Route-dependent",
        "peak_frequency": "Route-dependent",
        "timetable_url": "https://myrapid.com.my/bus-train/rapid-penang/rapid-pg-bus/",
        "match": ["penang rapid", "rapid penang"],
    },
    {
        "id": "kuantan",
        "name": "Rapid Kuantan",
        "mode": "bus",
        "operator": "Rapid Bus",
        "region": "Kuantan",
        "route": "Kuantan urban bus network",
        "service_hours": "Route-dependent",
        "peak_frequency": "Route-dependent",
        "timetable_url": "https://myrapid.com.my/bus-train/rapid-kuantan/",
        "match": ["rapid kuantan", "bas kuantan"],
    },
    {
        "id": "mybas",
        "name": "BAS.MY Network",
        "mode": "bus",
        "operator": "APAD-contracted operators",
        "region": "Selected Malaysian cities",
        "route": "City networks including Johor Bahru, Seremban and Ipoh",
        "service_hours": "Route-dependent",
        "peak_frequency": "Route-dependent",
        "timetable_url": "https://www.apad.gov.my/",
        "match": ["bas.my", "bas my", "mybas", "bas muafakat johor"],
    },
]

PLANNED_SERVICES: list[dict] = [
    {
        "id": "ecrl",
        "name": "East Coast Rail Link",
        "route": "Kota Bharu to Terminal Bersepadu Gombak",
        "stage": "Targeted for passenger operations from January 2027",
        "operator": "Malaysia Rail Link",
        "url": "https://ecrl.com.my/",
    },
    {
        "id": "rts-johor",
        "name": "RTS Link",
        "route": "Bukit Chagar to Woodlands North",
        "stage": "Under construction",
        "operator": "RTSO",
        "url": "https://www.mymrt.com.my/projects/rts-link/",
    },
    {
        "id": "mrt3",
        "name": "MRT3 Circle Line",
        "route": "51 km orbital line around Kuala Lumpur",
        "stage": "Final railway scheme approved; land acquisition underway",
        "operator": "MRT Corp",
        "url": "https://www.mymrt.com.my/projects/mrt3-circle-line/",
    },
    {
        "id": "penang-lrt",
        "name": "Penang LRT Mutiara Line",
        "route": "PSR-A to Komtar / Penang Sentral",
        "stage": "Under construction; operations expected in December 2031",
        "operator": "MRT Corp",
        "url": "https://laluanmutiara.mymrt.com.my/lrt-mutiara-line/",
    },
]

OFFICIAL_RSS_HOSTS = ("myrapid.com.my", "ktmb.com.my")
OFFICIAL_HANDLES = {"askrapidkl", "myrapidkl", "ktmb"}


def match_transport_line(cluster: dict) -> str | None:
    blob = " ".join(
        [
            cluster.get("entity") or "",
            cluster.get("location") or "",
            cluster.get("example_text") or cluster.get("normalized_text") or "",
            cluster.get("cluster_id") or "",
        ]
    ).lower()
    if cluster.get("subcategory") == "bus" and not any(
        _token_hit(marker, blob) for marker in ["kelana", "kajang", "mrt", "lrt", "ktm", "monorail", "brt"]
    ):
        if "penang" in blob:
            return "penang"
        if "kuantan" in blob:
            return "kuantan"
        if any(marker in blob for marker in ["bas.my", "bas my", "mybas"]):
            return "mybas"
        return "rapid-bus"
    generic_ids = {"ktm-komuter", "rapid-bus"}
    for line in sorted(LINE_CATALOG, key=lambda item: item["id"] in generic_ids):
        if any(_token_hit(token, blob) for token in line["match"]):
            return line["id"]
    return None


def is_official_grounding_row(row: dict) -> bool:
    platform = row.get("source_platform") or ""
    if platform == "official":
        return True
    if platform != "rss":
        return False
    url = (row.get("url") or "").lower()
    if any(host in url for host in OFFICIAL_RSS_HOSTS):
        return True
    handle = (row.get("author_handle") or "").lower().lstrip("@")
    return handle in OFFICIAL_HANDLES
