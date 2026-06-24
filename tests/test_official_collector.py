from datetime import UTC, datetime, timedelta

from app.collectors.official.client import _bing_myrapid_results, _extract_page_focus, _is_recent_enough, _looks_like_myrapid_alert_link, _myrapid_category, _parse_myrapid_date, _parse_myrapid_status_table_html
from app.collectors.common import soup_from_html


def test_extract_page_focus_prefers_service_update_text_over_navigation():
    html = """
    <html>
      <head><title>SERVICE UPDATE - MyRapid</title></head>
      <body>
        <nav>Home Bus Train Rapid KL Resources Contact Us</nav>
        <article>
          <h1>SERVICE UPDATE</h1>
          <p>Please be informed that due to peak hours, congestion is expected at interchange and connecting stations.</p>
          <p>Passengers at connecting stations may consider using alternative train routes via KL Sentral and Ampang Park.</p>
        </article>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """
    text = _extract_page_focus(
        soup_from_html(html),
        selectors=["h1", "article p", "p"],
        keywords=["service update", "congestion", "stations", "kl sentral", "ampang park"],
    )
    assert "service update" in text.lower()
    assert "congestion" in text.lower()
    assert "contact us" not in text.lower()


def test_extract_page_focus_can_fall_back_to_keyword_window():
    html = """
    <html>
      <head><title>Unifi Alerts</title></head>
      <body>
        <div>Random banner text</div>
        <section>
          Stay informed with real-time service disruption updates, affected areas, and restoration progress.
        </section>
      </body>
    </html>
    """
    text = _extract_page_focus(
        soup_from_html(html),
        selectors=[".does-not-exist"],
        keywords=["service disruption", "restoration progress"],
    )
    assert "service disruption" in text.lower()


def test_myrapid_alert_link_filter_accepts_real_alert_titles():
    assert _looks_like_myrapid_alert_link(
        "Kemas Kini Laluan Ampang/Sri Petaling",
        "https://myrapid.com.my/kemas-kini-laluan-ampang-sri-petaling-278/",
    )


def test_myrapid_alert_link_filter_rejects_non_alert_pages():
    assert not _looks_like_myrapid_alert_link(
        "Performance Update",
        "https://myrapid.com.my/myrapid-performance/",
    )


def test_myrapid_category_maps_rail_alerts_to_transport():
    category = _myrapid_category(
        "Kemas Kini Laluan Ampang/Sri Petaling",
        "Tren dari Sentul Timur beroperasi seperti biasa ke Putra Heights.",
    )
    assert category == "transport"


def test_parse_myrapid_date_normalizes_detail_page_date():
    assert _parse_myrapid_date("23 June, 2026") == "2026-06-23"


def test_bing_myrapid_results_extracts_alert_title_snippet_and_date():
    html = """
    <html>
      <body>
        <li class="b_algo">
          <h2><a href="https://myrapid.com.my/kelewatan-tren-laluan-ampang-sri-petaling-68/">Kelewatan Tren: Laluan Ampang/Sri Petaling - MyRapid</a></h2>
          <div class="b_caption"><p>Kelewatan Tren: Laluan Ampang/Sri Petaling. 1 June, 2026. Kerja-kerja baik pulih di Stesen Chan Sow Lin masih dijalankan.</p></div>
        </li>
      </body>
    </html>
    """
    results = _bing_myrapid_results(html)
    assert len(results) == 1
    assert results[0]["href"] == "https://myrapid.com.my/kelewatan-tren-laluan-ampang-sri-petaling-68/"
    assert results[0]["created_at"] == "2026-06-01"
    assert "Chan Sow Lin" in results[0]["body"]


def test_myrapid_recent_filter_rejects_old_alert_dates():
    assert _is_recent_enough("2022-11-08") is False


def test_myrapid_recent_filter_accepts_recent_alert_dates():
    recent = (datetime.now(UTC) - timedelta(days=7)).date().isoformat()
    assert _is_recent_enough(recent) is True


def test_parse_myrapid_status_table_html_keeps_only_non_normal_rows():
    html = """
    <html>
      <body>
        <table>
          <tr>
            <th>Service Line</th>
            <th>Status</th>
            <th>Remark</th>
          </tr>
          <tr>
            <td>Kelana Jaya Line</td>
            <td>Normal Service</td>
            <td></td>
          </tr>
          <tr>
            <td>Putrajaya Line</td>
            <td>Train Delays</td>
            <td>Manual operation near Kepong Baru</td>
          </tr>
        </table>
      </body>
    </html>
    """
    rows = _parse_myrapid_status_table_html(html)
    assert len(rows) == 1
    assert rows[0]["author_handle"] == "official:myrapid:status-table"
    assert "Putrajaya Line" in rows[0]["raw_text"]
    assert "Train Delays" in rows[0]["raw_text"]
