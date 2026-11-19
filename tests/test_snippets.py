from __future__ import annotations

from features.snippets import SnippetProvider, SnippetService, validate_snippet


def test_snippet_validation_and_crud(config, db, hooks):
    service = SnippetService(config, db, hooks)
    assert not validate_snippet({"title": "Missing content", "content": ""})[0]
    ok, message = service.save({
        "title": "Email signature",
        "category": "Work",
        "shortcut": "sig",
        "content": "Regards,\\nOkyanus",
    })
    assert ok, message
    rows = service.snippets()
    assert len(rows) == 1
    assert rows[0]["category"] == "Work"
    assert service.search("sig")[0]["title"] == "Email signature"

    snippet = rows[0]
    assert service.copy(snippet)
    assert hooks.calls[-1] == ("copy_text", ("Regards,\\nOkyanus",))
    service.delete(snippet["id"])
    assert service.snippets() == []


def test_snippet_provider_only_copies_on_explicit_selection(config, db, hooks):
    service = SnippetService(config, db, hooks)
    service.save({"title": "Greeting", "category": "General", "shortcut": "hello",
                  "content": "Hello there"})
    provider = SnippetProvider(config, db, hooks, service)
    results = provider.search("hello", 5)
    assert len(results) == 1
    assert hooks.calls == []
    results[0].execute()
    assert ("copy_text", ("Hello there",)) in hooks.calls


def test_snippets_persist_across_service_instances(config, db, hooks):
    first = SnippetService(config, db, hooks)
    first.save({"title": "Persisted", "content": "Saved text"})
    second = SnippetService(config, db, hooks)
    assert second.snippets()[0]["content"] == "Saved text"
