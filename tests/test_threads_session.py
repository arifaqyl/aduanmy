import json

from app.collectors.threads.client import _new_threads_context, _page_has_authenticated_session
from app.collectors.threads.session import load_storage_state, save_storage_state, session_status
from app.core.config import settings


def _state() -> dict:
    return {
        "cookies": [
            {"name": "sessionid", "value": "session-value", "domain": ".threads.com", "path": "/"},
            {"name": "csrftoken", "value": "csrf-value", "domain": ".threads.com", "path": "/"},
            {"name": "unrelated", "value": "drop-me", "domain": ".threads.com", "path": "/"},
        ],
        "origins": [{"origin": "https://example.com", "localStorage": [{"name": "x", "value": "y"}]}],
    }


def test_session_round_trip_keeps_only_required_cookie_scope(tmp_path, monkeypatch):
    path = tmp_path / "private" / "threads-session.json"
    monkeypatch.setattr(settings, "threads_session_path", str(path))

    save_storage_state(_state())
    loaded = load_storage_state()

    assert loaded is not None
    assert {cookie["name"] for cookie in loaded["cookies"]} == {"sessionid", "csrftoken"}
    assert loaded["origins"] == []
    assert session_status()["available"] is True


def test_session_rejects_missing_csrf_cookie(tmp_path, monkeypatch):
    path = tmp_path / "threads-session.json"
    monkeypatch.setattr(settings, "threads_session_path", str(path))
    path.write_text(
        json.dumps({"cookies": [{"name": "sessionid", "value": "x", "domain": ".threads.com"}]}),
        encoding="utf-8",
    )

    assert load_storage_state() is None
    assert session_status()["available"] is False


def test_browser_context_receives_session_state(monkeypatch):
    state = _state()
    monkeypatch.setattr("app.collectors.threads.client.load_storage_state", lambda: state)

    class Context:
        def __init__(self):
            self.options = None

        def set_default_timeout(self, _ms):
            pass

        def set_default_navigation_timeout(self, _ms):
            pass

    class Browser:
        options = None

        def __init__(self):
            self._context = Context()

        def new_context(self, **options):
            self.options = options
            self._context.options = options
            return self._context

    browser = Browser()
    context, authenticated = _new_threads_context(browser)

    assert context is browser._context
    assert authenticated is True
    assert browser.options["storage_state"] == state


def test_session_cookie_domain_does_not_accept_suffix_spoof(tmp_path, monkeypatch):
    path = tmp_path / "threads-session.json"
    monkeypatch.setattr(settings, "threads_session_path", str(path))
    spoofed = _state()
    for cookie in spoofed["cookies"]:
        cookie["domain"] = "evilthreads.com"

    save_storage_state(spoofed)

    assert path.exists() is False


def test_authenticated_page_requires_activity_nav_and_no_login():
    class Locator:
        def __init__(self, count):
            self._count = count

        def count(self):
            return self._count

    class Page:
        def __init__(self, activity=1, login_link=0, login_text=0):
            self.activity = activity
            self.login_link = login_link
            self.login_text = login_text

        def locator(self, selector):
            return Locator(self.activity if selector == "a[href='/activity']" else self.login_link)

        def get_by_text(self, _text, exact=False):
            return Locator(self.login_text)

    assert _page_has_authenticated_session(Page()) is True
    assert _page_has_authenticated_session(Page(activity=0)) is False
    assert _page_has_authenticated_session(Page(login_link=1)) is False
