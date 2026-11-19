from __future__ import annotations

from features.tasks import TaskProvider, TaskService


def test_task_validation_crud_due_dates_and_completion(config, db, hooks):
    service = TaskService(config, db, hooks)
    assert not service.save({"title": "", "due_date": ""})[0]
    assert not service.save({"title": "Bad date", "due_date": "tomorrow"})[0]

    ok, message = service.save({
        "title": "Prepare release",
        "notes": "Review the installer",
        "due_date": "2026-12-01",
    })
    assert ok, message
    task = service.tasks()[0]
    assert task["due_date"] == "2026-12-01"
    assert not task["completed"]

    service.complete(task["id"], True)
    assert service.tasks()[0]["completed"]
    assert service.tasks(include_completed=False) == []
    service.complete(task["id"], False)
    assert service.tasks(include_completed=False)[0]["title"] == "Prepare release"
    service.delete(task["id"])
    assert service.tasks() == []


def test_task_search_provider_offers_completion_action(config, db, hooks):
    service = TaskService(config, db, hooks)
    service.save({"title": "Review SeekR installer", "notes": "Check checksums"})
    provider = TaskProvider(config, db, hooks, service)
    results = provider.search("installer", 5)
    assert len(results) == 1
    assert results[0].title == "Review SeekR installer"
    assert any(action.label == "Mark complete" for action in results[0].actions)
    assert hooks.calls == []


def test_task_service_sorts_open_due_tasks_first(config, db, hooks):
    service = TaskService(config, db, hooks)
    service.save({"title": "No date"})
    service.save({"title": "Later", "due_date": "2027-01-01"})
    service.save({"title": "Soon", "due_date": "2026-11-20"})
    rows = service.tasks(include_completed=False)
    assert [row["title"] for row in rows] == ["Soon", "Later", "No date"]
