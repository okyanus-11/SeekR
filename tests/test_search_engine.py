from __future__ import annotations

import pytest

from core.models import SearchResult
from core.search_engine import SearchEngine, SearchProvider


class FakeProvider(SearchProvider):
    id = "fake"
    title = "Fake"
    keyword = "test"
    weight = 1.0
    auto = True

    def search(self, query, limit):
        if not query.strip():
            return []
        return [self.make_result(title=f"fake {query}", score=0.8, copy_text=query)]

    def suggestions(self, limit):
        return [self.make_result(title="fake suggestion", score=0.5)]

    def empty_help(self):
        return self.make_result(title="fake help", score=1.0)


class KeywordOnlyProvider(SearchProvider):
    id = "calc"
    title = "Calculator"
    keyword = "calc"
    weight = 1.2
    auto = False

    def search(self, query, limit):
        return [self.make_result(title="42", score=0.9)]


class ExplodingProvider(SearchProvider):
    id = "boom"
    title = "Boom"
    keyword = "boom"
    auto = True

    def search(self, query, limit):
        raise RuntimeError("provider exploded")


@pytest.fixture
def engine(config, db, hooks):
    engine = SearchEngine(config, db, hooks)
    engine.register(FakeProvider(config, db, hooks))
    engine.register(KeywordOnlyProvider(config, db, hooks))
    return engine


def test_keyword_resolution(engine):
    assert engine.resolve("test: hello")[0].id == "fake"
    assert engine.resolve("TEST:hello")[1] == "hello"
    assert engine.resolve("unknown: hello") is None
    assert engine.resolve("plain query") is None


def test_keyword_search_uses_remainder(engine):
    results = engine.search("test: something")
    assert results and results[0].title == "fake something"


def test_keyword_aliases(config, db, hooks):
    config.set("search.keyword_aliases", {"t": "test", "c": "calc"})
    engine = SearchEngine(config, db, hooks)
    engine.register(FakeProvider(config, db, hooks))
    engine.register(KeywordOnlyProvider(config, db, hooks))
    assert engine.resolve("t: hello")[0].id == "fake"
    assert engine.resolve("c: 2+2")[0].id == "calc"
    # Unknown alias target is ignored.
    config.set("search.keyword_aliases", {"x": "missing"})
    assert engine.resolve("x: hello") is None


def test_empty_keyword_uses_help(engine):
    results = engine.search("test:")
    assert results and results[0].title == "fake help"


def test_automatic_results_and_web_fallback(engine):
    results = engine.search("hello")
    titles = [result.title for result in results]
    assert "fake hello" in titles
    # Keyword-only providers do not run automatically.
    assert "42" not in titles


def test_disabled_provider(config, db, hooks):
    config.set("search.disabled_providers", ["fake"])
    engine = SearchEngine(config, db, hooks)
    engine.register(FakeProvider(config, db, hooks))
    results = engine.search("test: hello")
    assert results and "disabled" in results[0].title.lower()
    assert engine.search("hello") == []


def test_provider_errors_are_contained(config, db, hooks):
    engine = SearchEngine(config, db, hooks)
    engine.register(ExplodingProvider(config, db, hooks))
    results = engine.search("boom: query")
    assert results and results[0].category == "System"
    assert "unavailable" in results[0].title.lower()


def test_suggestions(engine):
    results = engine.suggestions()
    assert any(result.title == "fake suggestion" for result in results)


def test_keyword_hints(engine):
    results = engine.search("ca")
    hints = [result for result in results if result.category == "Keyword"]
    assert hints
    hints[0].execute()
    assert ("fill_query", ("calc: ",)) in engine.hooks.calls


def test_limit_is_respected(config, db, hooks):
    config.set("search.max_results", 3)
    engine = SearchEngine(config, db, hooks)
    engine.register(FakeProvider(config, db, hooks))
    results = engine.search("hello", limit=3)
    assert len(results) <= 3


def test_duplicate_results_are_removed(config, db, hooks):
    class DuplicateProvider(SearchProvider):
        id = "dup"
        keyword = "dup"
        auto = True
        weight = 1.0

        def search(self, query, limit):
            return [self.make_result(title="Same", score=0.5, subtitle="row")]

    engine = SearchEngine(config, db, hooks)
    engine.register(DuplicateProvider(config, db, hooks))
    engine.register(FakeProvider(config, db, hooks))
    results = engine.search("hello")
    assert len([result for result in results if result.title == "Same"]) == 1


def test_search_history_recording(engine):
    engine.record_search("hello world")
    engine.record_search("calc: 2+2")  # keyword queries are not stored
    assert engine.db.recent_queries(5) == ["hello world"]
    engine.config.set("privacy.save_search_history", False)
    engine.record_search("not stored")
    assert "not stored" not in engine.db.recent_queries(10)


def test_keyword_reference(engine):
    reference = engine.keyword_reference()
    assert reference
    assert all(result.category == "Keyword" for result in reference)



def test_keyword_map_is_cached_and_invalidated_by_alias_changes(engine):
    first = engine.keyword_map()
    assert engine.keyword_map() is first

    engine.config.set("search.keyword_aliases", {"t": "test"})
    second = engine.keyword_map()
    assert second is not first
    assert second["t"].id == "fake"


def test_register_and_unregister_invalidate_keyword_cache(engine, config, db, hooks):
    first = engine.keyword_map()
    extra = KeywordOnlyProvider(config, db, hooks)
    engine.unregister("calc")
    without_calc = engine.keyword_map()
    assert without_calc is not first
    assert "calc" not in without_calc

    engine.register(extra)
    with_calc = engine.keyword_map()
    assert with_calc is not without_calc
    assert with_calc["calc"].id == "calc"


def test_search_history_limit_prunes_all_older_rows(config, db, hooks):
    engine = SearchEngine(config, db, hooks)
    for index in range(250):
        db.add_history("search", f"query {index}")

    engine._trim_search_history(3)
    rows = db.history("search", 1000)
    assert len(rows) == 3
    assert [row["value"] for row in rows] == ["query 249", "query 248", "query 247"]
