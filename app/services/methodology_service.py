from __future__ import annotations

from app.core.freshness import LIVE_WINDOW_DAYS, RECENT_DAYS
from app.services.line_status_service import STATUS_WINDOW_HOURS, STATUS_WINDOW_MODE


def get_methodology() -> dict:
    return {
        "product": "TrafficMY",
        "scope": "malaysia",
        "not_official": True,
        "disclaimer_ms": (
            "TrafficMY bukan laman rasmi RapidKL, Prasarana, atau KTMB. "
            "Ini papan status isyarat awam — bukan pengesahan operasi."
        ),
        "disclaimer_en": (
            "TrafficMY is not an official RapidKL, Prasarana, or KTMB site. "
            "This is a public-signal status board — not operational confirmation."
        ),
        "sources": [
            {
                "id": "threads",
                "label": "Threads",
                "role": "public_signal",
                "note_ms": "Carian kata kunci pengangkutan Malaysia; laporan penumpang.",
                "note_en": "Keyword search for Malaysia transport; passenger reports.",
            },
            {
                "id": "reddit",
                "label": "Reddit",
                "role": "public_signal",
                "note_ms": "r/malaysia dan komuniti berkaitan — sokongan tambahan.",
                "note_en": "r/malaysia and related communities — supplementary signals.",
            },
            {
                "id": "rss",
                "label": "RSS / berita",
                "role": "media_report",
                "note_ms": "Google News RSS; bukan rasmi melainkan pautan myrapid.com.my / ktmb.com.my.",
                "note_en": "Google News RSS; not official unless linked to myrapid.com.my / ktmb.com.my.",
            },
            {
                "id": "official",
                "label": "MyRapid / KTMB",
                "role": "official_grounding",
                "note_ms": "Halaman & carian rasmi untuk corroboration — tidak dipaparkan sebagai aduan.",
                "note_en": "Official pages and search for corroboration — not shown as complaints.",
            },
            {
                "id": "gtfs_rt",
                "label": "GTFS-RT (bas)",
                "role": "telemetry",
                "note_ms": "Isyarat GPS bas sahaja; bukan kebenaran gangguan LRT/MRT.",
                "note_en": "Bus GPS signals only; not confirmation of LRT/MRT disruption.",
            },
        ],
        "severity_levels": [
            {
                "id": "unknown",
                "label_ms": "Tiada isyarat semasa",
                "label_en": "No current signal",
                "meaning_ms": "Tiada bukti terkini melepasi penapis; ini bukan pengesahan perkhidmatan normal.",
                "meaning_en": "No recent evidence passed the filter; this is not confirmation of normal service.",
            },
            {
                "id": "minor",
                "label_ms": "Laporan kecil",
                "label_en": "Minor reports",
                "meaning_ms": "Isyarat lemah atau tunggal; usia terkini.",
                "meaning_en": "Weak or single signals; recent age.",
            },
            {
                "id": "delay",
                "label_ms": "Kelewatan dilaporkan",
                "label_en": "Delays reported",
                "meaning_ms": "Kata kunci kelewatan / lambat / rosak dalam cluster.",
                "meaning_en": "Delay / slow / breakdown keywords in the cluster.",
            },
            {
                "id": "disruption",
                "label_ms": "Gangguan",
                "label_en": "Disruption",
                "meaning_ms": "Gangguan besar, terhenti, atau kecemasan.",
                "meaning_en": "Major disruption, suspension, or emergency language.",
            },
        ],
        "windows": {
            "status_window_mode": STATUS_WINDOW_MODE,
            "status_window_hours": STATUS_WINDOW_HOURS,
            "status_window_note_en": "Line status and Live today feed reset at midnight MYT. After last train, lines show Ended for today.",
            "status_window_note_ms": "Status laluan dan suapan Live today reset tengah malam MYT. Selepas tren terakhir, laluan tunjuk Tamat hari ini.",
            "recent_days": RECENT_DAYS,
            "live_window_days": LIVE_WINDOW_DAYS,
            "stale_after_minutes_default": 180,
        },
        "corroboration": {
            "badge_ms": "Rasmi",
            "badge_en": "Official",
            "rule_ms": (
                "Lencana ✓ Rasmi apabila sumber rasmi MyRapid/KTMB atau RSS rasmi "
                "sepadan dengan laluan yang sama seperti cluster sosial."
            ),
            "rule_en": (
                "The ✓ Official badge appears when an official MyRapid/KTMB source or official RSS "
                "matches the same line within the 24-hour corroboration window."
            ),
        },
        "quality_gate": {
            "summary_ms": (
                "Bukan setiap post yang menyebut LRT/MRT dimasukkan. "
                "Penapis quality_only menolak ulasan gaya hidup, balasan thread, dan isyarat bukan masalah."
            ),
            "summary_en": (
                "Not every post mentioning LRT/MRT is included. "
                "The filter rejects lifestyle chatter, speculative questions, thread replies, and non-issue signals. "
                "Raw wording and usernames are never republished."
            ),
        },
        "ingest_schedule": {
            "manual_refresh_note_en": "The dashboard reloads the latest snapshot; collection runs automatically on the server.",
            "threads_duration_note_en": "A collection can take several minutes without blocking dashboard readers.",
        },
        "inspired_by": ["TfL Line Status", "SuperNYC Subway", "Citymapper fusion", "Transit.app severity"],
    }
