from __future__ import annotations

from features.web_search import LANGUAGES, TranslateProvider, WebProvider, WebService


def test_default_url_building(config, hooks, db):
    service = WebService(config, hooks, db)
    url = service.build_url("hello world")
    assert url == "https://duckduckgo.com/?q=hello+world"
    assert service.build_url("a&b") == "https://duckduckgo.com/?q=a%26b"


def test_engine_urls(config, hooks):
    service = WebService(config, hooks)
    assert "google.com/search" in service.build_url("cats", "google")
    assert "youtube.com/results" in service.build_url("lofi", "youtube")
    assert "wikipedia.org" in service.build_url("ESP32", "wikipedia")
    assert "github.com/search" in service.build_url("seekr", "github")
    assert service.engine_label("github") == "GitHub"


def test_custom_engine(config, hooks):
    config.set(
        "web.engines",
        {"searx": {"label": "SearX", "url": "https://searx.example/search?q={query}"}},
    )
    service = WebService(config, hooks)
    assert service.build_url("test", "searx") == "https://searx.example/search?q=test"
    config.set("web.engine", "searx")
    assert service.default_engine() == "searx"
    # Unknown engine falls back to the default.
    assert "searx.example" in service.build_url("x", "nope")


def test_open_uses_hooks(config, hooks, db):
    service = WebService(config, hooks, db)
    ok, message = service.open("seekr launcher", "google")
    assert ok and "google" in message.lower() or "opened" in message.lower()
    assert hooks.calls[-1][0] == "open_url"
    assert "google.com" in hooks.calls[-1][1][0]
    assert db.history("web")


def test_web_provider_results(config, hooks, db):
    service = WebService(config, hooks, db)
    provider = WebProvider(config, db, hooks, service)
    results = provider.search("seekr", 5)
    assert results
    assert "DuckDuckGo" in results[0].title
    assert results[0].copy_text.startswith("https://")
    assert provider.search("", 5) == []


def test_translate_provider(config, hooks, db):
    service = WebService(config, hooks, db)
    provider = TranslateProvider(config, db, hooks, service)
    results = provider.search("Hello to Turkish", 5)
    assert results
    url = results[0].meta["url"]
    assert "tl=tr" in url and "text=Hello" in url
    assert LANGUAGES["turkish"] == "tr"
    help_result = provider.search("just text", 5)
    assert help_result and "Translate text" in help_result[0].title


def test_translate_execute_opens_url(config, hooks, db):
    provider = TranslateProvider(config, db, hooks, WebService(config, hooks, db))
    results = provider.search("Good morning to German", 5)
    results[0].execute()
    opened = [call for call in hooks.calls if call[0] == "open_url"]
    assert opened and "tl=de" in opened[-1][1][0]


def test_web_provider_open_failure(config, db, hooks):
    class FailingHooks:
        def open_url(self, url):
            return False

        def hide_launcher(self):
            pass

        def notify(self, *args, **kwargs):
            pass

    service = WebService(config, FailingHooks())
    ok, message = service.open("anything")
    assert not ok and "http" in message
