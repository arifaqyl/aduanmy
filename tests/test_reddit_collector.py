from datetime import UTC, datetime, timedelta

from app.collectors.reddit.client import (
    _category_prefilter,
    _curated_seed_rows,
    _extract_external_article_excerpt,
    _extract_reddit_post_payload,
    _is_recent_enough,
    _matches_query,
    _trim_reddit_boilerplate,
)


def test_reddit_matches_query_for_real_telco_outage():
    text = "Unifi down all week in kelantan and home internet keeps shutting off"
    assert _matches_query(text, "unifi down")
    assert _category_prefilter(text, "telco_internet")


def test_reddit_category_prefilter_rejects_property_rant_with_incidental_unifi():
    text = (
        "Avoid GSD Land nightmare post-VP. No major internet providers like Unifi and Time are available "
        "in this property even after a year."
    )
    assert not _category_prefilter(text, "telco_internet")


def test_reddit_category_prefilter_rejects_telco_entertainment_post():
    text = "HBO channels ceased broadcasting on Astro and may be pulled from Unifi TV as well"
    assert not _category_prefilter(text, "telco_internet")


def test_reddit_category_prefilter_rejects_celcomdigi_ekyc_rant():
    text = (
        "CelcomDigi app asked for facial verification and ID check, then said face not valid and "
        "session reached its limit."
    )
    assert not _category_prefilter(text, "telco_internet")


def test_reddit_category_prefilter_rejects_transport_history_discussion():
    text = (
        "Bus routes in Kuala Lumpur and Selangor before 1998. I am compiling a list of operators "
        "and routes from memory."
    )
    assert not _category_prefilter(text, "transport")


def test_reddit_category_prefilter_rejects_flood_ghost_story_noise():
    text = (
        "I am feeling spooky. Let me share a ghost story from kampung. The road was always banjir "
        "and there was mercun near the kubur."
    )
    assert not _category_prefilter(text, "flood_weather")


def test_curated_seed_rows_drop_stale_telco_fallbacks():
    rows = _curated_seed_rows()
    telco_rows = [row for row in rows if row["seed_category"] == "telco_internet"]
    assert telco_rows == []


def test_curated_seed_rows_include_current_transport_delay_seed():
    rows = _curated_seed_rows()
    transport_rows = [row for row in rows if row["seed_category"] == "transport"]
    assert any("kelana jaya line can expect delays" in row["raw_text"].lower() for row in transport_rows)
    current = next(row for row in transport_rows if "can expect delays" in row["raw_text"].lower())
    assert current["created_at"] == "2026-06-24T03:35:05+00:00"
    assert current["author_handle"] == "MajlisPerbandaranKL"


def test_trim_reddit_boilerplate_removes_subreddit_furniture():
    text = (
        "LRT Kelana Jaya line having problems again this morning. This is getting too frequent. "
        "A subreddit about Malaysia and all things Malaysian. New to reddit? Read this first!"
    )
    trimmed = _trim_reddit_boilerplate(text)
    assert "subreddit about malaysia" not in trimmed.lower()
    assert trimmed.endswith("too frequent.")


def test_extract_reddit_post_payload_parses_exact_post_html(monkeypatch):
    html = """
    <html><body>
      <a class="title">Commuters On Kelana Jaya Line Can Expect Delays</a>
      <a class="author">MajlisPerbandaranKL</a>
      <time datetime="2026-06-24T03:35:05+00:00"></time>
      <div class="thing link">
        <div class="usertext-body">
          <div class="md">
            <p>Rapid KL says trains are delayed after a technical fault near KLCC.</p>
          </div>
        </div>
      </div>
    </body></html>
    """

    monkeypatch.setattr("app.collectors.reddit.client.fetch_html", lambda url, timeout=10: html)

    payload = _extract_reddit_post_payload("https://old.reddit.com/r/malaysia/comments/example")

    assert payload["title"] == "Commuters On Kelana Jaya Line Can Expect Delays"
    assert payload["author_handle"] == "MajlisPerbandaranKL"
    assert payload["created_at"] == "2026-06-24T03:35:05+00:00"
    assert "technical fault near KLCC" in payload["body"]


def test_extract_external_article_excerpt_keeps_transport_paragraphs(monkeypatch):
    html = """
    <html><body>
      <p>Rapid KL has advised commuters on the Kelana Jaya Line to expect delays following technical issues involving a train's brake system.</p>
      <p>In a separate incident, a train at Pasar Seni Station is being manually operated due to a door system malfunction.</p>
      <p>About us and company address.</p>
    </body></html>
    """
    monkeypatch.setattr("app.collectors.reddit.client.fetch_html", lambda url, timeout=12: html)
    excerpt = _extract_external_article_excerpt("https://example.com/article")
    assert "Kelana Jaya Line" in excerpt
    assert "Pasar Seni Station" in excerpt


def test_reddit_recent_filter_rejects_old_posts():
    assert _is_recent_enough("2026-05-01T03:35:05+00:00") is False


def test_reddit_recent_filter_accepts_recent_posts():
    recent = (datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z")
    assert _is_recent_enough(recent) is True
