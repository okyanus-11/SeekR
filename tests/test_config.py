from __future__ import annotations

import json

from core.config_manager import ConfigManager, default_config, sanitize


def test_defaults_are_complete(config):
    assert config.get("general.hotkey") == "Alt+Space"
    assert config.get("appearance.theme") == "dark"
    assert config.get("search.max_results") == 12
    assert config.get("files.directories") == default_config()["files"]["directories"]


def test_set_and_persist(tmp_path):
    path = tmp_path / "config.json"
    config = ConfigManager(path)
    config.set("appearance.theme", "dracula")
    config.set("appearance.opacity", 0.8)
    config.set("apps_alias_check", "ignored")
    assert path.exists()

    reloaded = ConfigManager(path)
    assert reloaded.get("appearance.theme") == "dracula"
    assert reloaded.get("appearance.opacity") == 0.8
    assert "apps_alias_check" in reloaded.data  # unknown keys survive round-trips


def test_invalid_values_are_sanitised(config):
    config.set("appearance.theme", "not-a-theme")
    assert config.get("appearance.theme") == "dark"
    config.set("general.hotkey", "Space")
    assert config.get("general.hotkey") == "Alt+Space"
    config.set("general.hotkey", "ctrl+shift+k")
    assert config.get("general.hotkey") == "Ctrl+Shift+K"
    config.set("search.max_results", 9999)
    assert config.get("search.max_results") == 50
    config.set("search.max_results", "abc")
    assert config.get("search.max_results") == 3
    config.set("appearance.opacity", 5)
    assert config.get("appearance.opacity") == 1.0
    config.set("appearance.accent", "#abc")
    assert config.get("appearance.accent") == "#aabbcc"
    config.set("appearance.accent", "not-a-color")
    assert config.get("appearance.accent") == "#7c5cff"
    config.set("search.disabled_providers", "web")
    assert config.get("search.disabled_providers") == []


def test_nested_lists_are_coerced(config):
    config.set("files.directories", [123, 456])
    assert config.get("files.directories") == ["123", "456"]
    config.set("applications.excluded", "not a list")
    assert config.get("applications.excluded") == []


def test_corrupt_config_recovers(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ not valid json", encoding="utf-8")
    config = ConfigManager(path)
    assert config.get("general.hotkey") == "Alt+Space"
    assert (tmp_path / "config.corrupt.json").exists()


def test_reset_restores_defaults(config):
    config.set("appearance.theme", "nord")
    config.reset()
    assert config.get("appearance.theme") == "dark"


def test_sanitize_handles_wrong_root_type():
    result = sanitize("nonsense")
    assert result["general"]["hotkey"] == "Alt+Space"


def test_aliases_are_validated(config):
    config.set("search.keyword_aliases", {"W": ["web"], "bad": "web"})
    assert config.get("search.keyword_aliases") == {"w": "web", "bad": "web"}
    config.set("search.keyword_aliases", {"x": 5})
    assert config.get("search.keyword_aliases") == {}
    config.set("search.keyword_aliases", "not-a-dict")
    assert config.get("search.keyword_aliases") == {}


def test_saved_file_is_valid_json(config, tmp_path):
    config.set("appearance.accent", "#112233")
    payload = json.loads(config.path.read_text(encoding="utf-8"))
    assert payload["appearance"]["accent"] == "#112233"
