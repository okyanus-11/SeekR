from __future__ import annotations

import os
import sys

import pytest

from core.models import ResultAction
from features.commands import CommandEntry, CommandService, CommandsProvider


@pytest.fixture
def service(config, db, hooks):
    return CommandService(config, db, hooks)


def test_builtin_commands_present(service):
    keys = {entry.key for entry in service.builtins()}
    for expected in ("shutdown", "restart", "sleep", "lock", "settings", "taskmgr", "terminal", "explorer", "ipconfig", "empty_recycle"):
        assert expected in keys


def test_destructive_commands_flagged(service):
    entries = {entry.key: entry for entry in service.builtins()}
    assert entries["shutdown"].destructive
    assert entries["restart"].destructive
    assert entries["empty_recycle"].destructive
    assert not entries["ipconfig"].destructive


def test_needs_confirmation_respects_config(service):
    shutdown = next(entry for entry in service.builtins() if entry.key == "shutdown")
    assert service.needs_confirmation(shutdown)
    service.config.set("commands.confirm_destructive", False)
    assert not service.needs_confirmation(shutdown)


def test_builtin_search(service):
    results = service.search("ipconfig")
    assert results and results[0].key == "ipconfig"
    assert service.search("nothing-like-this") == []
    assert len(service.search("")) == min(8, len(service.entries()))


def test_unsupported_builtins_fail_gracefully(service):
    if os.name == "nt":
        pytest.skip("Only meaningful off Windows")
    shutdown = next(entry for entry in service.builtins() if entry.key == "shutdown")
    outcome = service.run(shutdown)
    assert not outcome.success
    assert "not supported" in outcome.message.lower()


def test_custom_command_validation(service):
    ok, message = service.validate_custom({"name": "", "command": "/bin/echo"})
    assert not ok and "name" in message.lower()
    ok, message = service.validate_custom({"name": "Echo", "command": ""})
    assert not ok
    ok, message = service.validate_custom({"name": "Echo", "command": "definitely-not-a-real-binary-xyz"})
    assert not ok and "not found" in message.lower()
    executable = sys.executable if os.name == "nt" else "/bin/echo"
    ok, message = service.validate_custom({"name": "Echo", "command": executable})
    assert ok, message


def test_custom_command_cannot_smuggle_a_shell(service):
    ok, _ = service.validate_custom({"name": "Bad", "command": "echo hello; rm -rf /"})
    assert not ok


def test_custom_command_run_and_history(service):
    executable = sys.executable if os.name == "nt" else "/bin/echo"
    ok, message = service.save_custom(
        {"name": "Echo test", "command": executable, "args": "hello", "aliases": "echo", "confirm": False}
    )
    assert ok, message
    entries = service.custom_commands()
    assert entries and entries[0].title == "Echo test"
    outcome = service.run(entries[0], "extra")
    assert outcome.success
    assert service.history()
    assert "Echo test" in service.history()[0]


def test_custom_commands_survive_restart(config, db, hooks):
    service = CommandService(config, db, hooks)
    service.save_custom({"name": "Persisted", "command": sys.executable, "args": "", "confirm": True})
    other = CommandService(config, db, hooks)
    assert any(entry.title == "Persisted" for entry in other.custom_commands())


def test_provider_destructive_requires_confirmation(service, hooks, config, db):
    provider = CommandsProvider(config, db, hooks, service)
    shutdown = next(entry for entry in service.builtins() if entry.key == "shutdown")
    results = provider.search("shutdown", 5)
    assert results
    results[0].execute()
    assert any(call[0] == "confirm" for call in hooks.calls)
    # NullHooks declines confirmation, so nothing runs and no history is written.
    assert not db.history("command")


def test_provider_lists_commands_when_empty(service, config, db, hooks):
    provider = CommandsProvider(config, db, hooks, service)
    results = provider.search("", 5)
    assert len(results) == 5


def test_provider_no_match_help(service, config, db, hooks):
    provider = CommandsProvider(config, db, hooks, service)
    results = provider.search("zzzzzz", 5)
    assert results and "No command matches" in results[0].title


def test_provider_custom_commands(service, config, db, hooks):
    service.save_custom({"name": "Say hi", "command": sys.executable, "args": "-c pass", "confirm": False})
    provider = CommandsProvider(config, db, hooks, service)
    results = provider.search("say hi", 5)
    assert results and results[0].title == "Say hi"
    assert any(action.label == "Edit command" for action in results[0].actions)

def test_command_chain_runs_known_commands_in_order(service, hooks):
    from features.commands import CommandOutcome

    calls = []
    service._handlers["taskmgr"] = lambda args: (calls.append(("taskmgr", args)) or CommandOutcome(True, "Task Manager opened"))
    service._handlers["explorer"] = lambda args: (calls.append(("explorer", args)) or CommandOutcome(True, "Explorer opened"))
    outcome = service.run_chain("taskmgr then explorer")
    assert outcome.success
    assert calls == [("taskmgr", []), ("explorer", [])]
    assert len(service.history()) == 2


def test_command_chain_stops_on_unknown_step(service):
    from features.commands import CommandOutcome

    calls = []
    service._handlers["taskmgr"] = lambda args: (calls.append("taskmgr") or CommandOutcome(True, "ok"))
    outcome = service.run_chain("taskmgr then not-a-real-command")
    assert not outcome.success
    # The complete chain is validated before any step executes.
    assert calls == []
    assert "unknown command" in outcome.message.lower()


def test_command_chain_requires_confirmation_for_destructive_steps(service, hooks):
    from features.commands import CommandOutcome

    calls = []
    service._handlers["empty_recycle"] = lambda args: (calls.append("empty") or CommandOutcome(True, "emptied"))
    outcome = service.run_chain("empty_recycle then taskmgr")
    assert not outcome.success
    assert calls == []
    assert any(name == "confirm" for name, _args in hooks.calls)


def test_command_chain_provider_is_explicit(service, config, db, hooks):
    from features.commands import CommandChainProvider

    provider = CommandChainProvider(config, db, hooks, service)
    result = provider.search("taskmgr then explorer", 5)
    assert len(result) == 1
    assert "2 command steps" in result[0].title

def test_command_chain_resolves_multiword_alias_and_custom_title(service, hooks):
    from features.commands import CommandOutcome

    calls = []
    hooks.confirm = lambda *_args: True
    service._handlers["empty_recycle"] = lambda args: (calls.append(("empty", args)) or CommandOutcome(True, "done"))
    outcome = service.run_chain("empty trash")
    assert outcome.success
    assert calls == [("empty", [])]


def test_command_chain_separator_ignores_quoted_then_text():
    from features.commands import split_command_chain

    assert split_command_chain('taskmgr "then this is an argument" then explorer') == [
        'taskmgr "then this is an argument"', "explorer"
    ]


def test_command_chain_preview_resolves_every_step_without_execution(service):
    valid, message, plan = service.preview_chain("taskmgr then empty trash")
    assert valid, message
    lines, resolved = plan
    assert len(lines) == 2
    assert "Task Manager" in lines[0] or "taskmgr" in lines[0].lower()
    assert "confirmation required" in lines[1]
    assert len(resolved) == 2
