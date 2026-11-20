from __future__ import annotations

import json

from core.config_manager import ConfigManager, default_config, sanitize


def test_defaults_are_complete(config):
    assert config.get("general.hotkey") == "Alt+Space"
    assert config.get("appearance.theme") == "dark"
    assert config.get("search.max_results") == 12
    assert config.get("widgets.clock_enabled") is True
    assert config.get("widgets.weather_enabled") is True
    assert config.get("widgets.system_enabled") is True
    assert config.get("widgets.cat_enabled") is True
    assert config.get("widgets.weather_location") == ""
    assert config.get("appearance.window_width") == 1180
    assert config.get("files.directories") == default_config()["files"]["directories"]
    assert config.get("clipboard.enabled") is False
    assert config.get("privacy.clipboard_history") is False
    assert config.get("privacy.clipboard_history_consent") is False


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


def test_v1_config_migrates_default_launcher_dimensions(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema_version": 1, "appearance": {"window_width": 780, "window_height": 500}}), encoding="utf-8")
    config = ConfigManager(path)
    assert config.get("schema_version") == 2
    assert config.get("appearance.window_width") == 1180
    assert config.get("appearance.window_height") == 620

def test_v1_config_preserves_custom_launcher_dimensions(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema_version": 1, "appearance": {"window_width": 920, "window_height": 540}}), encoding="utf-8")
    config = ConfigManager(path)
    assert config.get("appearance.window_width") == 920
    assert config.get("appearance.window_height") == 540

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
    assert config.get("appearance.accent") == "#68a9ff"
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
    assert config.reset() is True
    assert config.get("appearance.theme") == "dark"


def test_reset_reports_persistence_failure(config, monkeypatch):
    config.set("appearance.theme", "nord", save=False)
    monkeypatch.setattr(config, "save", lambda: False)
    assert config.reset() is False
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



def test_malformed_schema_version_recovers_as_legacy_config(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"schema_version": "not-a-number", "appearance": {"window_width": 780, "window_height": 500}}),
        encoding="utf-8",
    )
    config = ConfigManager(path)
    assert config.get("schema_version") == 2
    assert config.get("appearance.window_width") == 1180
    assert config.get("appearance.window_height") == 620


def test_v1_config_migrates_numeric_string_default_dimensions(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({
            "schema_version": 1,
            "appearance": {"window_width": "780", "window_height": "500"},
        }),
        encoding="utf-8",
    )
    config = ConfigManager(path)
    assert config.get("appearance.window_width") == 1180
    assert config.get("appearance.window_height") == 620



def test_widget_layout_settings_are_bounded_and_normalized(config):
    config.set("widgets.rail_width", 999)
    assert config.get("widgets.rail_width") == 280
    config.set("widgets.card_height", 1)
    assert config.get("widgets.card_height") == 124
    config.set("widgets.left_order", ["tasks", "clock", "tasks", "unknown"])
    assert config.get("widgets.left_order") == ["tasks", "clock", "system"]
    config.set("widgets.right_order", ["cat", "cat", "invalid"])
    assert config.get("widgets.right_order") == ["cat", "weather", "media"]


def test_widget_layout_settings_survive_config_reload(tmp_path):
    path = tmp_path / "config.json"
    config = ConfigManager(path)
    config.set("widgets.rail_width", 224)
    config.set("widgets.card_height", 180)
    config.set("widgets.left_order", ["tasks", "system", "clock"])
    loaded = ConfigManager(path)
    assert loaded.get("widgets.rail_width") == 224
    assert loaded.get("widgets.card_height") == 180
    assert loaded.get("widgets.left_order") == ["tasks", "system", "clock"]


def test_legacy_daily_widget_settings_migrate_to_cat(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "schema_version": 2,
        "widgets": {
            "meme_enabled": False,
            "right_order": ["meme", "weather", "media"],
        },
    }), encoding="utf-8")
    config = ConfigManager(path)
    assert config.get("widgets.cat_enabled") is False
    assert config.get("widgets.right_order") == ["cat", "weather", "media"]
    assert "meme_enabled" not in config.data["widgets"]
    assert "meme_refresh_minutes" not in config.data["widgets"]
