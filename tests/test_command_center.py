from __future__ import annotations

from features.command_center import CommandCenterProvider


def test_command_center_finds_workflow_and_system_actions(config, db, hooks):
    provider = CommandCenterProvider(config, db, hooks)
    workflows = provider.search("workflow", 5)
    assert workflows
    assert workflows[0].title == "Workflow manager"
    system = provider.search("system", 5)
    assert any(result.title == "System monitor" for result in system)


def test_command_center_widget_toggle_updates_config(config, db, hooks):
    provider = CommandCenterProvider(config, db, hooks)
    before = bool(config.get("widgets.clock_enabled", True))
    results = provider.search("toggle clock widget", 5)
    result = next(item for item in results if item.title == "Toggle clock widget")
    result.execute()
    assert bool(config.get("widgets.clock_enabled", True)) is (not before)
    assert any(name == "notify" for name, _args in hooks.calls)


def test_command_center_search_shortcut_fills_launcher_query(config, db, hooks):
    provider = CommandCenterProvider(config, db, hooks)
    results = provider.search("search file contents", 5)
    result = next(item for item in results if item.title == "Search file contents")
    result.execute()
    assert hooks.calls[-1] == ("fill_query", ("content: ",))
