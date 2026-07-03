from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from app.collectors.rss import client as rss_client

_RECENT_PUBDATE = (datetime.now(UTC) - timedelta(days=1)).strftime("%a, %d %b %Y %H:%M:%S GMT")

SAMPLE_RSS = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>Kelana Jaya Line delay causes commuter frustration</title>
      <link>https://example.com/kjl-delay</link>
      <pubDate>{_RECENT_PUBDATE}</pubDate>
      <description>Rapid KL reports delays on the Kelana Jaya Line due to technical fault.</description>
    </item>
    <item>
      <title>World Cup promo for Rapid KL riders</title>
      <link>https://example.com/promo</link>
      <pubDate>{_RECENT_PUBDATE}</pubDate>
      <description>Watch all matches on your commute.</description>
    </item>
  </channel>
</rss>
"""

MOCK_FEED = [
    {
        "url": "https://example.com/feed.xml",
        "category": "transport",
        "author_handle": "google-news:test",
    }
]


def test_rss_collector_filters_transport_and_skips_promo(monkeypatch):
    with patch.object(rss_client, "rss_feeds", return_value=MOCK_FEED):
        with patch.object(rss_client, "fetch_html", return_value=SAMPLE_RSS):
            rows = rss_client.collect_rss_sample()

    assert len(rows) == 1
    assert rows[0]["source_platform"] == "rss"
    assert rows[0]["seed_category"] == "transport"
    assert "kelana jaya" in rows[0]["raw_text"].lower()


def test_rss_parse_handles_malformed_xml():
    assert rss_client._parse_rss_items("not xml") == []
