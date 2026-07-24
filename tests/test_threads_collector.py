from datetime import UTC, datetime, timedelta

from app.core.freshness import myt_day_start


def _recent_today_iso() -> str:
    """A timestamp guaranteed to fall on today's MYT calendar date, regardless of
    what wall-clock time the test suite happens to run at (avoids midnight-boundary
    flakiness from a fixed "N hours ago" delta)."""
    return (myt_day_start() + timedelta(hours=1)).isoformat().replace("+00:00", "Z")


from app.collectors.threads.client import (
    _apply_text_created_at,
    _clean_search_preview,
    _fill_missing_created_at,
    _is_recent_enough,
    _is_profile_discovery_candidate,
    _is_search_result_candidate,
    _is_usable_threads_row,
    _is_watchlist_candidate,
    _looks_like_aggregated_feed_preview,
    _looks_like_foreign_platform_outage,
    _looks_like_pinned_preview,
    _looks_like_reply_thread_blob,
    _looks_like_threads_signup_bait,
    _sort_rows_by_created_at,
    _scrape_threads_search_page,
    _strip_leading_handle_time,
    _transport_queries_for_run,
)
from app.pipeline.extract import (
    category_signal_ok,
    transport_incident_signal_ok,
    transport_rider_signal_worthwhile,
)


def test_transport_query_rotation_keeps_core_and_lrt3_coverage():
    from app.collectors.discovery import discovery_config, threads_queries
    from app.collectors.threads.client import MANDATORY_TRANSPORT_QUERIES

    queries = _transport_queries_for_run()
    assert queries[:5] == list(MANDATORY_TRANSPORT_QUERIES)
    assert len(queries) == 8
    available = set(threads_queries("transport"))
    assert set(queries[5:]).issubset(available)
    # Full config still carries LRT3 / KTM terms even when depth-sliced for a single run.
    full = set(discovery_config().get("threads_queries", {}).get("transport", []))
    assert any("lrt3" in q for q in full)
    assert any("ktm" in q for q in full)


def test_threads_search_uses_recent_results_tab():
    class EmptyLocator:
        def evaluate_all(self, _script):
            return []

    class Mouse:
        def wheel(self, _x, _y):
            pass

    class Page:
        def __init__(self):
            self.url = ""
            self.mouse = Mouse()

        def goto(self, url, **_kwargs):
            self.url = url

        def wait_for_timeout(self, _milliseconds):
            pass

        def locator(self, _selector):
            return EmptyLocator()

    page = Page()
    _scrape_threads_search_page(page, "lrt3 shah alam")

    assert "filter=recent" in page.url


def test_looks_like_threads_signup_bait_flags_login_prompts():
    assert _looks_like_threads_signup_bait("Join Threads to share ideas, ask questions, post random thoughts")
    assert not _looks_like_threads_signup_bait("Tak boleh keluar stesen fire alarm kat MRT Maluri")


def test_is_usable_threads_row_rejects_aggregated_feed_preview():
    assert not _is_usable_threads_row(
        {"raw_text": "afifah.hgm 3h Me every single time iam.anamaro 15h POV: Me when I don't have unifi"}
    )


def test_is_usable_threads_row_rejects_signup_bait():
    assert not _is_usable_threads_row({"raw_text": "Join Threads to share ideas"})
    assert _is_usable_threads_row({"raw_text": "Kelana Jaya line delay at Bangsar"})


def test_is_usable_threads_row_rejects_reply_thread_blob():
    blob = "lelzilla45 06/16/26 Replying to @rapidkl why is the train stuck at Bangsar for 20 minutes"
    assert _looks_like_reply_thread_blob(blob)
    assert not _is_usable_threads_row({"raw_text": blob, "seed_category": "transport"})


def test_foreign_platform_outage_rejected_for_telco_search():
    text = "Facebook down worldwide again today"
    assert _looks_like_foreign_platform_outage(text, "telco_internet")
    assert not _is_search_result_candidate(text, "telco_internet")
    assert _is_search_result_candidate("Unifi down again in Shah Alam", "telco_internet")


def test_apply_text_created_at_uses_raw_text():
    row = {"raw_text": "05 June 2026: Kelana Jaya Line incident update", "created_at": ""}
    _apply_text_created_at(row)
    assert row["created_at"] == "2026-06-05T00:00:00Z"


def test_fill_missing_created_at_backfills_only_missing_rows(monkeypatch):
    rows = [
        {"url": "https://threads.example/post/1", "created_at": ""},
        {"url": "https://threads.example/post/2", "created_at": "2026-06-21T04:18:43.000Z"},
    ]

    def fake_timestamps(urls: list[str]) -> dict[str, str]:
        assert urls == ["https://threads.example/post/1"]
        return {"https://threads.example/post/1": "2026-06-22T10:10:46.000Z"}

    monkeypatch.setattr("app.collectors.threads.client._playwright_post_timestamps", fake_timestamps)

    filled = _fill_missing_created_at(rows)

    assert filled[0]["created_at"] == "2026-06-22T10:10:46.000Z"
    assert filled[1]["created_at"] == "2026-06-21T04:18:43.000Z"


def test_looks_like_pinned_preview_flags_pinned_rows():
    assert _looks_like_pinned_preview("Pinned transit.taste.trail 05/14/26 something")
    assert not _looks_like_pinned_preview("transit.taste.trail 16h Tak boleh keluar stesen")


def test_profile_discovery_candidate_is_strict_for_transport():
    assert _is_profile_discovery_candidate(
        "transit.taste.trail 16h Tak boleh keluar stesen",
        "Tak boleh keluar stesen fire alarm kat MRT Maluri",
        "transport",
    )
    assert not _is_profile_discovery_candidate(
        "transit.taste.trail 1d Exit gate pulak problem",
        "",
        "transport",
    )
    assert not _is_profile_discovery_candidate(
        "transit.taste.trail 1d Jom jalan-jalan LRT3",
        "",
        "transport",
    )


def test_transport_incident_signal_accepts_live_line_breakdown_post():
    text = "Korang Mrt Kajang line problem ke? kenape tak gerak2 ni..."
    assert transport_incident_signal_ok(text)
    assert category_signal_ok(text, "transport", "Kajang Line")


def test_transport_incident_signal_rejects_property_and_lifestyle_mentions():
    assert not transport_incident_signal_ok(
        "FOR SALE condo dekat LRT Cempaka below market asking price RM235,000."
    )
    assert not transport_incident_signal_ok(
        "Located in Menara UOA Bangsar and connected with LRT Bangsar, serving really good pastries."
    )
    assert not transport_incident_signal_ok(
        "lelzilla45 06/16/26 Replying to @lelzilla45 LRT Chan Sow Lin station is nice"
    )
    assert not transport_incident_signal_ok(
        "People are saying goodbye to Astro. Everyone running to Unifi."
    )


def test_transport_rider_signal_rejects_speculative_opinion_all_lines():
    """Future/predictive debate and sarcastic wait — any line, not LRT3-only phrases."""
    posts = [
        # Original LRT3 false positive
        "Dgn 3 koc tren LRT3 tu ko tunggu je la dia akan ada problem cepat rosak mcm LRT2 KJ. "
        "Keh3. Kos penjimatan konon. Tp sebab keputusan bodoh",
        "nabiledler92 20h Dgn 3 koc tren LRT3 tu ko tunggu je la dia akan ada problem cepat rosak",
        "Makin lama lah menunggu tren. Semua sebab benda yg dah expected akan jadi bila downscope.",
        # Same failure mode on other lines
        "KTM komuter ko tunggu je la nanti akan rosak macam dulu jugak",
        "MRT Kajang akan ada problem cepat rosak lepas 10 tahun guna",
        "Monorail downscope memang akan delay lagi nanti kalau maintenance kurang",
        "Kelana Jaya line expected akan jadi macam hell bila kekerapan tren kurang",
        "budakwang 21m If MRT Putrajaya will become like Pasar Seni when crowd picks up?",
    ]
    for text in posts:
        assert not transport_incident_signal_ok(text), text[:60]
        assert not transport_rider_signal_worthwhile(text), text[:60]


def test_transport_rider_signal_accepts_live_waiting_all_lines():
    """Real rider waits still pass after tightening weak-term gates."""
    assert transport_rider_signal_worthwhile(
        "KTM stuck tadi dekat KL Sentral, kena tunggu 40 minit"
    )
    assert transport_rider_signal_worthwhile(
        "Kelana Jaya Line delay sekarang, menunggu tren dekat Bangsar station"
    )
    assert transport_rider_signal_worthwhile(
        "MRT Kajang rosak tadi, tunggu lama dekat platform Kwasa Damansara"
    )


def test_transport_incident_signal_rejects_hypothetical_and_advisory_posts():
    assert not transport_incident_signal_ok(
        "Bayangkan LRT3 dah start operate lepastu KJ line ada problem/delay, "
        "station Glenmarie akan jd macam Pasar Seni?",
        "Kelana Jaya Line",
    )
    assert not transport_incident_signal_ok(
        "Commuters on the Kelana Jaya Line can expect delays.",
        "Kelana Jaya Line",
    )
    assert not transport_incident_signal_ok(
        "What if MRT Kajang line will become like Pasar Seni when LRT3 opens?",
    )
    assert not transport_incident_signal_ok(
        "Lrt kelana jaya line harini tak padat sangat, ramai WFH sebab takut train problem ke?",
        "Kelana Jaya Line",
    )
    assert not transport_incident_signal_ok("LRT delay tak tu? Jalan jem tak tu? Jangan stress pagi ni")


def test_transport_incident_signal_rejects_generic_chatter():
    assert not transport_rider_signal_worthwhile("Kelana Jaya Line delay memang teruk")
    assert not transport_rider_signal_worthwhile("Korang rasa MRT Kajang selalu delay tak?")
    assert not transport_rider_signal_worthwhile("Throwback dulu LRT Ampang selalu rosak")
    assert not transport_rider_signal_worthwhile("Unpopular opinion: RapidKL delay hari2")


def test_transport_rider_signal_rejects_latest_threads_false_positives():
    assert not transport_rider_signal_worthwhile(
        "That magnificent finish by Mbappe is a great example of how the game could be improved "
        "by changing the offside rule. Or... he could just delay his run, like every other striker."
    )
    assert not transport_rider_signal_worthwhile(
        "Lord, go before me and make every crooked path straight. Where there has been delay, "
        "bring divine acceleration."
    )
    assert not transport_rider_signal_worthwhile(
        "Rebuilding requires you to show up daily. Each day that passes by with no work put in "
        "is another day that delays the finish line."
    )
    assert not transport_rider_signal_worthwhile(
        "Gold Line is operating on a 12 minute westbound delay due to a track blockage."
    )
    assert not transport_rider_signal_worthwhile(
        "benda ni hype awal2 je sis. sy dah rasa mrt kajang 2017. bila dah byk issue, "
        "tak maintenance, tobat dah nak naik. nak ke office kena tukar line lrt kelana jaya"
    )
    assert not transport_rider_signal_worthwhile(
        "Harini ramai orang belakang tabir LRT 3 post gambar. Kalau LRT problem, "
        "janganlah maki-maki orang bawah."
    )
    assert not transport_rider_signal_worthwhile(
        "LRT3 Shah Alam Line Day 1 experience. Glenmarie ke TRX, 60 minit, 2 pertukaran laluan."
    )


def test_transport_rider_signal_rejects_qa_false_positives():
    assert not transport_rider_signal_worthwhile("Dah lambat. Sesak.")
    assert not transport_rider_signal_worthwhile(
        "RM277 billion PTPTN debt is enough to build a whole new LRT4 line for Malaysia"
    )
    assert not transport_rider_signal_worthwhile(
        "My Selangorku rumah mampu milik harga rumah naik, nak beli rumah dekat LRT station pun susah"
    )
    assert not transport_rider_signal_worthwhile(
        "45 minute tunggu grab from MRT Kwasa Damansara station pagi ni"
    )
    assert not transport_rider_signal_worthwhile(
        "LRT3 was delayed multiple times over years in development before opening"
    )
    assert not transport_rider_signal_worthwhile(
        "Not recommend naik KTM Komuter, better MRT or LRT laju timing sgt lambat ye"
    )
    assert not transport_rider_signal_worthwhile(
        "budakwang 21m Rasuah is still a big problem. Malaysia lost RM277b due to corruption. enough to build a whole new LRT4"
    )
    assert not transport_rider_signal_worthwhile(
        "How long do we have to cope with this RapidKL? sikit2 delay bagaii"
    )
    assert not transport_rider_signal_worthwhile(
        "dandihusnah 10h Kecik sangat kalau sama size dgn kelana jaya line. X function kalau rumah sebelah lrt. Cuma yg terpaling terdesak je guna lrt. Dah lambat. Sesak. Apa faedah guna lrt?"
    )
    assert not transport_rider_signal_worthwhile(
        "Dah kau kenselkan 5 stesen dan kecikkan saiz, pastu pulak 6 gerabak kau potong jadi 3 gerabak. Tu bukan jimat."
    )
    assert transport_rider_signal_worthwhile(
        "Kelana Jaya Line delay again, waiting 25 minutes at Bangsar station hari ni"
    )


def test_transport_incident_signal_accepts_concrete_current_evidence():
    assert transport_rider_signal_worthwhile("Kelana Jaya Line delay again, waiting 25 minutes at Bangsar")
    assert transport_rider_signal_worthwhile("MRT Kajang delay due to a signal failure")
    assert transport_rider_signal_worthwhile("LRT Ampang tak gerak sekarang, penuh dekat platform")
    assert transport_rider_signal_worthwhile(
        "Kelana Jaya Line delay 20 min petang ni kat Bangsar"
    )
    assert transport_rider_signal_worthwhile(
        "MRT Kajang stuck dalam tren malam ni, waiting 15 minutes"
    )
    from app.pipeline.extract import TRANSPORT_TODAY_RIDER_TERMS

    for cue in ("petang ni", "malam ni", "dalam tren", "kat stesen"):
        assert cue in TRANSPORT_TODAY_RIDER_TERMS
    assert not transport_rider_signal_worthwhile(
        "Throwback dulu Kelana Jaya Line delay was crazy, waiting 25 minutes at Bangsar"
    )
    assert transport_rider_signal_worthwhile(
        "Kepada yang stuck traffic jam drpd Kg Melayu Subang menuju ke MRT Kwasa, guna jalan alternatif"
    )
    assert transport_rider_signal_worthwhile(
        "Lrt kelana jaya line elok smpai masjid jamek ko tak bukak pintu lepas tu jalan je. "
        "sampai pasar seni jem dgn manusia, extra cost hari ni, sampai lambat ke opis"
    )
    assert transport_rider_signal_worthwhile(
        "LRT buat hal harini. Train duk jerking after KLCC station. Sampai Masjid Jamek stop lama, "
        "pintu tak buka. Manusia dah macam semut dekat platform."
    )


def test_transport_incident_signal_rejects_generic_delay_word_outside_transit_context():
    # Real production false positives (2026-07-02 QA sample): a bare place-name
    # match ("Selangor", "Putrajaya") plus a generic word like "delay"/"problem"
    # used to be enough to look like a live transit incident.
    assert not transport_incident_signal_ok(
        "kays.lists Kalau mengakali sistem mah curang lah kak. Itu kan voucher kompensasi "
        "keterlambatan yang akan cust dapat kl memang ada delay pengiriman lewat dari "
        "estimasi packing dari toko."
    )
    assert not transport_incident_signal_ok(
        "Ibu bapa di area KL & Cheras yang tercari-cari servis Terapi Cara Kerja (OT) di rumah, "
        "slot dengan OT ALSHAHFIKA kini dibuka! Sangat sesuai untuk anak yang ada delay, "
        "masalah sensori, Autism, atau ADHD."
    )
    assert not transport_incident_signal_ok(
        "Boleh save contact saya. Saya nak juga cari circle bisnes baru.. Especially di KL dan "
        "Selangor. jabbalsinarservices Saya pembekal Fire alarm panel. Product Dari Italy."
    )
    assert not transport_incident_signal_ok(
        "Hi, ada tak makeup canvas yg available? Location Petaling Jaya. -got your personal "
        "transport -fair to medium tan skin w minimal skin problem"
    )
    assert not transport_incident_signal_ok(
        "Give IM Adrenaline into the anterolateral thigh without delay. Adults: 500 micrograms "
        "(0.5 mL of 1:1000). Repeat every 5 minutes if symptoms persist."
    )


def test_transport_incident_signal_rejects_ambiguous_place_name_without_line_word():
    # "Putrajaya" and "Kajang" are both MRT lines *and* everyday place names.
    # A bare mention with an unrelated "lambat/penuh" should not count as a
    # transit-line mention unless paired with an actual mode/line word.
    assert not transport_incident_signal_ok(
        "PRESINT 11, PUTRAJAYA Ramai yang WhatsApp bila slot dah penuh. CLOSED ORDER (250 pax). "
        "Kalau nak makan minggu depan, lock slot dari sekarang. Siapa lambat, kena tunggu slot "
        "seterusnya."
    )
    assert transport_incident_signal_ok("MRT Putrajaya problem, stuck dekat stesen TRX dari tadi.")
    assert transport_incident_signal_ok("putrajaya line rosak lagi? stop lama wei!! still at conlay")


def test_transport_incident_signal_word_boundary_avoids_line_substring_false_positive():
    # "line" is a substring of many unrelated English words (adrenaline,
    # tickets->ets, streets->ets). Naive substring matching used to treat
    # those as transit mentions.
    assert not transport_incident_signal_ok(
        "AND usually skin or mucosal changes. Give IM Adrenaline into the anterolateral thigh "
        "without delay. Adults: 500 micrograms, repeat every 5 minutes if symptoms persist."
    )
    assert not transport_incident_signal_ok(
        "Selalu delay beli tickets kat closets warehouse sale, streets penuh orang beratur."
    )


def test_extract_bus_route_ignores_unrelated_numbers():
    from app.pipeline.extract import extract_bus_route

    assert extract_bus_route("CLOSED ORDER (250 pax) siapa lambat kena tunggu slot seterusnya") == ""
    assert extract_bus_route(
        "Give IM Adrenaline without delay. Adults: 500 micrograms, repeat every 5 minutes."
    ) == ""


def test_threads_recent_filter_rejects_old_posts():
    assert _is_recent_enough("2025-11-14T10:00:00Z") is False


def test_threads_recent_filter_accepts_recent_posts():
    # RECENT_WINDOW_DAYS is 1 — same-day rider reports only.
    recent = _recent_today_iso()
    assert _is_recent_enough(recent) is True


def test_threads_recent_filter_rejects_four_day_old_posts():
    old = (datetime.now(UTC) - timedelta(days=4)).isoformat().replace("+00:00", "Z")
    assert _is_recent_enough(old) is False


def test_threads_recent_filter_rejects_two_day_old_posts():
    old = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    assert _is_recent_enough(old) is False


def test_is_watchlist_candidate_news_role_is_strict_for_transport():
    assert _is_watchlist_candidate(
        "Kelana Jaya line delay after train brake failure",
        "",
        "transport",
        "news",
    )
    assert not _is_watchlist_candidate(
        "Best nasi lemak near LRT Bangsar",
        "",
        "transport",
        "news",
    )


def test_sort_rows_by_created_at_orders_newest_first():
    rows = [
        {"created_at": "2026-06-20T10:00:00Z"},
        {"created_at": "2026-06-25T10:00:00Z"},
        {"created_at": ""},
    ]
    sorted_rows = _sort_rows_by_created_at(rows)
    assert sorted_rows[0]["created_at"] == "2026-06-25T10:00:00Z"
    assert sorted_rows[-1]["created_at"] == ""


def test_clean_search_preview_picks_complaint_line():
    preview = "damelias\nLrt kelana jaya line\n4d\nHi guys, LRT still problem ke?\n1\n3"
    assert _clean_search_preview(preview) == "Hi guys, LRT still problem ke?"


def test_is_search_result_candidate_accepts_transport_complaint():
    assert _is_search_result_candidate("Hi guys, LRT still delayed and not moving at Bangsar", "transport")
    assert not _is_search_result_candidate("Hi guys, LRT still problem ke?", "transport")
    assert not _is_search_result_candidate("Best nasi lemak near LRT Bangsar", "transport")


def test_collect_threads_sample_prioritizes_keyword_search(monkeypatch):
    calls: list[str] = []
    recent = _recent_today_iso()

    def fake_keyword(seen, **kwargs):
        calls.append("keyword")
        return [{"url": "https://threads.com/@a/post/1", "raw_text": "LRT still delayed, waiting 20 minutes at Bangsar", "created_at": recent, "query": "lrt problem", "seed_category": "transport", "source_platform": "threads", "post_id": "abc", "author_handle": "a"}]

    def fake_watchlist(seen):
        calls.append("watchlist")
        return []

    def fake_web(seen):
        calls.append("web")
        return []

    def fake_seed(seen, skip_profile_discovery=False):
        calls.append("seed")
        return []

    monkeypatch.setattr("app.collectors.threads.client._collect_keyword_search_posts", fake_keyword)
    monkeypatch.setattr("app.collectors.threads.client._collect_latest_watchlist_posts", fake_watchlist)
    monkeypatch.setattr("app.collectors.threads.client._collect_search_discovered_posts", fake_web)
    monkeypatch.setattr("app.collectors.threads.client._collect_seed_posts", fake_seed)
    monkeypatch.setattr("app.collectors.threads.client._fill_missing_created_at", lambda rows, deadline=None: rows)

    from app.collectors.threads.client import collect_threads_sample

    rows = collect_threads_sample()
    assert calls == ["keyword", "watchlist", "web", "seed"]
    assert len(rows) == 1
    assert rows[0]["query"] == "lrt problem"


def test_collect_threads_sample_skips_watchlist_when_keyword_enough(monkeypatch):
    recent = _recent_today_iso()

    def fake_keyword(seen, **kwargs):
        return [
            {
                "url": f"https://threads.com/@a/post/{i}",
                "raw_text": f"LRT delay again, waiting {i + 10} minutes at Bangsar",
                "created_at": recent,
                "query": "lrt problem",
                "seed_category": "transport",
                "source_platform": "threads",
                "post_id": f"abc{i}",
                "author_handle": "a",
            }
            for i in range(6)
        ]

    monkeypatch.setattr("app.collectors.threads.client._collect_keyword_search_posts", fake_keyword)
    monkeypatch.setattr(
        "app.collectors.threads.client._collect_latest_watchlist_posts",
        lambda seen: (_ for _ in ()).throw(AssertionError("watchlist should be skipped")),
    )
    monkeypatch.setattr("app.collectors.threads.client._collect_seed_posts", lambda seen, skip_profile_discovery=False: [])
    monkeypatch.setattr("app.collectors.threads.client._fill_missing_created_at", lambda rows, deadline=None: rows)
    monkeypatch.setattr(
        "app.collectors.threads.client.get_threads_diagnostics",
        lambda: {"reasons": [], "keyword_search_queries_with_hits": 6},
    )

    from app.collectors.threads.client import collect_threads_sample

    rows = collect_threads_sample()
    assert len(rows) == 6


def test_collect_threads_sample_runs_watchlist_when_keyword_rows_undated(monkeypatch):
    calls: list[str] = []
    recent = _recent_today_iso()

    def fake_keyword(seen, **kwargs):
        calls.append("keyword")
        return [
            {
                "url": f"https://threads.com/@a/post/{i}",
                "raw_text": f"LRT delay again, waiting {i + 10} minutes at Bangsar",
                "created_at": "",
                "query": "lrt problem",
                "seed_category": "transport",
                "source_platform": "threads",
                "post_id": f"abc{i}",
                "author_handle": "a",
            }
            for i in range(6)
        ]

    def fake_watchlist(seen):
        calls.append("watchlist")
        return [
            {
                "url": "https://threads.com/@b/post/1",
                "raw_text": "MRT delay now, waiting 15 minutes at Maluri",
                "created_at": recent,
                "query": "latest_profile",
                "seed_category": "transport",
                "source_platform": "threads",
                "post_id": "wl1",
                "author_handle": "b",
            }
        ]

    monkeypatch.setattr("app.collectors.threads.client._collect_keyword_search_posts", fake_keyword)
    monkeypatch.setattr("app.collectors.threads.client._collect_latest_watchlist_posts", fake_watchlist)
    monkeypatch.setattr("app.collectors.threads.client._collect_search_discovered_posts", lambda seen: [])
    monkeypatch.setattr("app.collectors.threads.client._collect_seed_posts", lambda seen, skip_profile_discovery=False: [])
    monkeypatch.setattr("app.collectors.threads.client._fill_missing_created_at", lambda rows, deadline=None: rows)
    monkeypatch.setattr(
        "app.collectors.threads.client.get_threads_diagnostics",
        lambda: {"reasons": [], "keyword_search_queries_with_hits": 6},
    )

    from app.collectors.threads.client import collect_threads_sample

    rows = collect_threads_sample()
    assert "watchlist" in calls
    assert any(r.get("query") == "latest_profile" for r in rows)

def test_collect_threads_sample_prioritizes_watchlist(monkeypatch):
    calls: list[str] = []
    recent = _recent_today_iso()

    def fake_keyword(seen, **kwargs):
        calls.append("keyword")
        return []

    def fake_watchlist(seen):
        calls.append("watchlist")
        return [{"url": "https://threads.com/@a/post/1", "raw_text": "MRT delay now, waiting 15 minutes at Maluri", "created_at": recent, "query": "latest_profile", "seed_category": "transport", "source_platform": "threads", "post_id": "abc", "author_handle": "a"}]

    def fake_web(seen):
        calls.append("web")
        return []

    def fake_seed(seen, skip_profile_discovery=False):
        calls.append("seed")
        return []

    monkeypatch.setattr("app.collectors.threads.client._collect_keyword_search_posts", fake_keyword)
    monkeypatch.setattr("app.collectors.threads.client._collect_latest_watchlist_posts", fake_watchlist)
    monkeypatch.setattr("app.collectors.threads.client._collect_search_discovered_posts", fake_web)
    monkeypatch.setattr("app.collectors.threads.client._collect_seed_posts", fake_seed)
    monkeypatch.setattr("app.collectors.threads.client._fill_missing_created_at", lambda rows, deadline=None: rows)

    from app.collectors.threads.client import collect_threads_sample

    rows = collect_threads_sample()
    assert calls[0] == "keyword"
    assert len(rows) == 1
    assert rows[0]["query"] == "latest_profile"


def test_transit_launch_bypass():
    from app.pipeline.extract import transport_line_info_signal_ok
    # Non-transit posts with free rides are still blocked
    assert not transport_line_info_signal_ok("Get your free rides at the theme park today")

    # Any transit line bypasses these blocks for launch/opening updates
    assert transport_line_info_signal_ok("LRT Kelana Jaya free rides today")
    assert transport_line_info_signal_ok("LRT Kelana Jaya line start operations today")
    assert transport_line_info_signal_ok("LRT3 free rides today")
    assert transport_line_info_signal_ok("LRT3 line start operations today")


def test_strip_leading_handle_time_removes_scrape_chrome():
    # Threads' DOM glues "<handle> <relative_time>" onto the caption with no
    # separator; a username fragment like ".stuck" or ".delayed" must not be
    # readable as post content by downstream keyword filters.
    raw = "pixel.stuck 9m Another hard race on msc_obernheim for the MXOpen boys"
    assert _strip_leading_handle_time(raw) == "Another hard race on msc_obernheim for the MXOpen boys"


def test_strip_leading_handle_time_leaves_normal_captions_alone():
    caption = "LRT Kelana Jaya stuck at Bangsar for 20 minutes now"
    assert _strip_leading_handle_time(caption) == caption


def test_unrelated_foreign_motocross_post_is_not_a_transport_signal():
    """Regression: a Threads search hit for KTM-brand motocross content in
    Switzerland was misread as a Malaysian rail incident. Two contributing
    bugs: (1) the scraped preview glued the author handle "pixel.stuck" onto
    the caption, so a naive "stuck" substring check fired on the username,
    and (2) the "@ktm_switzerland" handle mention matched a bare "ktm" token
    without a word boundary. Both must stay fixed."""
    raw = (
        "pixel.stuck 9m Another hard race on msc_obernheim for the MXOpen boys "
        "msc_obernheim sam_schweiz mxmagazine.ch ktm_switzerland kawasakischweiz "
        "#motocross #motocrosslife #raceday"
    )
    cleaned = _strip_leading_handle_time(raw)
    assert not transport_incident_signal_ok(cleaned)
    assert not transport_rider_signal_worthwhile(cleaned)
