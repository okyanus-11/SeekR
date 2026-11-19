from __future__ import annotations

import os

from features.window_manager import PROTECTED_PROCESS_NAMES, WindowManagerProvider, close_window, tile_window
from features.window_search import WindowProvider


def test_window_manager_rejects_invalid_targets_and_sides():
    ok, message = tile_window(0, "left")
    assert not ok
    assert message
    ok, message = tile_window(123, "diagonal")
    assert not ok
    assert message
    ok, message = close_window(0)
    assert not ok
    assert message


def test_window_manager_provider_is_explicit(config, db, hooks):
    provider = WindowManagerProvider(config, db, hooks)
    results = provider.search("minimize all", 5)
    assert results
    if os.name != "nt":
        assert "Windows-only" in results[0].title
    else:
        assert "Minimize all" in results[0].title


def test_window_search_offers_per_window_management_actions(config, db, hooks):
    provider = WindowProvider(config, db, hooks)
    result = provider._result({"hwnd": 123, "title": "Editor", "process": "editor.exe", "pid": 42}, 0.9)
    labels = {action.label for action in result.actions}
    assert {"Tile left", "Tile right", "Close window…"} <= labels
    # Close is guarded by confirmation before any native close request.
    close_action = next(action for action in result.actions if action.label == "Close window…")
    close_action.callback()
    assert any(name == "confirm" for name, _args in hooks.calls)

def test_window_manager_protects_shell_process_names():
    assert "explorer.exe" in PROTECTED_PROCESS_NAMES
    assert "dwm.exe" in PROTECTED_PROCESS_NAMES
    assert "winlogon.exe" in PROTECTED_PROCESS_NAMES
