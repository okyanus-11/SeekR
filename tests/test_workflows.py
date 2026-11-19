from __future__ import annotations

import json

from core.workers import CancelToken
from features.workflows import WorkflowService, validate_workflow


def test_workflow_validation_rejects_shell_and_unknown_steps(tmp_path):
    folder = tmp_path / "project"
    folder.mkdir()
    assert validate_workflow({
        "title": "Open project",
        "steps": [{"type": "open_folder", "path": str(folder)}],
    })[0]
    ok, message = validate_workflow({
        "title": "Unsafe",
        "steps": [{"type": "shell", "command": "whoami"}],
    })
    assert not ok
    assert "Unsupported" in message


def test_workflow_save_export_import_and_execute(config, db, hooks, tmp_path):
    folder = tmp_path / "project"
    folder.mkdir()
    service = WorkflowService(config, db, hooks)
    data = {
        "title": "Start project",
        "description": "Open the project and copy its path",
        "steps": [
            {"type": "open_folder", "path": str(folder)},
            {"type": "open_url", "url": "https://example.com"},
            {"type": "copy_text", "text": str(folder)},
        ],
    }
    ok, message = service.save(data)
    assert ok, message
    rows = service.workflows()
    assert len(rows) == 1
    assert rows[0]["steps"] == data["steps"]

    progress = []
    ok, message, completed = service.run(rows[0], on_progress=lambda *args: progress.append(args))
    assert ok, message
    assert completed == 3
    assert len(progress) == 3
    assert [name for name, _args in hooks.calls] == ["open_path", "open_url", "copy_text"]

    exported = service.export_json()
    imported_db = type(db)(":memory:")
    try:
        imported = WorkflowService(config, imported_db, hooks)
        ok, message, count = imported.import_json(exported)
        assert ok, message
        assert count == 1
        assert imported.workflows()[0]["title"] == "Start project"
    finally:
        imported_db.close()


def test_workflow_import_validates_all_before_writing(config, db, hooks):
    service = WorkflowService(config, db, hooks)
    payload = {
        "schema_version": 1,
        "workflows": [
            {"title": "Valid", "steps": [{"type": "copy_text", "text": "hello"}]},
            {"title": "Invalid", "steps": [{"type": "run_python", "code": "x"}]},
        ],
    }
    ok, _message, count = service.import_json(json.dumps(payload))
    assert not ok
    assert count == 0
    assert service.workflows() == []


def test_workflow_can_be_cancelled_before_first_step(config, db, hooks):
    service = WorkflowService(config, db, hooks)
    token = CancelToken()
    token.cancel()
    workflow = {"title": "Cancelled", "steps": [{"type": "copy_text", "text": "no"}]}
    ok, message, completed = service.run(workflow, token=token)
    assert not ok
    assert message == "Workflow cancelled"
    assert completed == 0
    assert hooks.calls == []

def test_workflow_provider_exposes_saved_flows_explicitly(config, db, hooks, tmp_path):
    from features.workflows import WorkflowProvider

    folder = tmp_path / "workspace"
    folder.mkdir()
    service = WorkflowService(config, db, hooks)
    service.save({"title": "Open workspace", "description": "Start working",
                  "steps": [{"type": "open_folder", "path": str(folder)}]})
    provider = WorkflowProvider(config, db, hooks, service)
    results = provider.search("workspace", 5)
    assert len(results) == 1
    assert results[0].title == "Open workspace"
    assert any(action.label == "Edit workflows" for action in results[0].actions)


def test_workflow_copy_step_failure_stops_chain(config, db, hooks):
    service = WorkflowService(config, db, hooks)
    hooks.copy_text = lambda _text: False
    workflow = {"title": "Copy", "steps": [{"type": "copy_text", "text": "hello"}]}
    ok, message, completed = service.run(workflow)
    assert not ok
    assert completed == 0
    assert "Could not copy text" in message


def test_workflow_rejects_malformed_urls_and_directory_as_executable(tmp_path):
    from features.workflows import validate_workflow

    ok, _ = validate_workflow({"title": "Bad URL", "steps": [{"type": "open_url", "url": "https://"}]})
    assert not ok
    ok, _ = validate_workflow({"title": "Bad executable", "steps": [
        {"type": "launch_app", "executable": str(tmp_path), "args": []}
    ]})
    assert not ok


def test_workflow_import_rejects_oversized_payload(config, db, hooks):
    from features.workflows import MAX_IMPORT_BYTES

    service = WorkflowService(config, db, hooks)
    ok, message, count = service.import_json(" " * (MAX_IMPORT_BYTES + 1))
    assert not ok
    assert count == 0
    assert "too large" in message.lower()


