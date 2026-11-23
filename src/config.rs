use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};
use serde_json::Value;
use tempfile::NamedTempFile;


/// Resolve the per-user configuration file without writing into the install directory.
pub fn config_path() -> PathBuf {
    if let Some(override_path) = std::env::var_os("SEEKR_CONFIG") {
        return PathBuf::from(override_path);
    }

    #[cfg(target_os = "windows")]
    {
        let base = std::env::var_os("APPDATA")
            .map(PathBuf::from)
            .or_else(|| std::env::var_os("USERPROFILE").map(|home| PathBuf::from(home).join("AppData").join("Roaming")))
            .unwrap_or_else(|| PathBuf::from("."));
        base.join("SeekR").join("config.json")
    }

    #[cfg(target_os = "macos")]
    {
        let base = std::env::var_os("HOME").map(PathBuf::from).unwrap_or_else(|| PathBuf::from("."));
        base.join("Library").join("Application Support").join("SeekR").join("config.json")
    }

    #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
    {
        let base = std::env::var_os("XDG_CONFIG_HOME")
            .map(PathBuf::from)
            .or_else(|| std::env::var_os("HOME").map(|home| PathBuf::from(home).join(".config")))
            .unwrap_or_else(|| PathBuf::from("."));
        base.join("SeekR").join("config.json")
    }
}

const WIDGETS: &[&str] = &["clock", "system", "tasks", "weather", "cat", "media"];

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct WidgetPreferences {
    pub rail_width: u16,
    pub card_height: u16,
    pub refresh_seconds: u16,
    pub enabled: BTreeMap<String, bool>,
    pub left_order: Vec<String>,
    pub right_order: Vec<String>,
    /// Preserve settings written by older SeekR versions that this build does not yet understand.
    #[serde(flatten)]
    pub legacy: BTreeMap<String, Value>,
}

impl Default for WidgetPreferences {
    fn default() -> Self {
        let enabled = WIDGETS.iter()
            .map(|name| ((*name).to_string(), !matches!(*name, "media")))
            .collect();
        Self {
            rail_width: 196,
            card_height: 140,
            refresh_seconds: 10,
            enabled,
            left_order: vec!["clock".into(), "system".into(), "tasks".into()],
            right_order: vec!["weather".into(), "cat".into(), "media".into()],
            legacy: BTreeMap::new(),
        }
    }
}

impl WidgetPreferences {
    pub fn normalize(&mut self) {
        if let Some(value) = self.legacy.get("rail_width").and_then(Value::as_u64) {
            self.rail_width = value.min(u16::MAX as u64) as u16;
        }
        if let Some(value) = self.legacy.get("card_height").and_then(Value::as_u64) {
            self.card_height = value.min(u16::MAX as u64) as u16;
        }
        if let Some(value) = self.legacy.get("left_order").and_then(Value::as_array) {
            self.left_order = value.iter().filter_map(Value::as_str).map(str::to_owned).collect();
        }
        if let Some(value) = self.legacy.get("right_order").and_then(Value::as_array) {
            self.right_order = value.iter().filter_map(Value::as_str).map(str::to_owned).collect();
        }

        self.rail_width = self.rail_width.clamp(160, 320);
        self.card_height = self.card_height.clamp(100, 260);
        self.refresh_seconds = self.refresh_seconds.clamp(5, 3600);

        let mut seen = HashSet::new();
        let mut left = Vec::new();
        let mut right = Vec::new();
        for name in self.left_order.drain(..) {
            if WIDGETS.contains(&name.as_str()) && seen.insert(name.clone()) { left.push(name); }
        }
        for name in self.right_order.drain(..) {
            if WIDGETS.contains(&name.as_str()) && seen.insert(name.clone()) { right.push(name); }
        }
        for name in WIDGETS {
            if seen.insert((*name).to_string()) { right.push((*name).to_string()); }
        }
        self.left_order = left;
        self.right_order = right;

        for name in WIDGETS {
            self.enabled.entry((*name).to_string()).or_insert(!matches!(*name, "media"));
        }
        self.enabled.retain(|name, _| WIDGETS.contains(&name.as_str()));

        // Keep legacy flat keys synchronized for safe downgrade/dual-version use.
        for (old_key, new_key) in [
            ("clock_enabled", "clock"),
            ("system_enabled", "system"),
            ("tasks_enabled", "tasks"),
            ("weather_enabled", "weather"),
            ("cat_enabled", "cat"),
            ("media_enabled", "media"),
        ] {
            // Only maintain compatibility keys that already existed in a
            // legacy config. New configs stay in the canonical nested format.
            if self.legacy.contains_key(old_key)
                && let Some(value) = self.enabled.get(new_key)
            {
                self.legacy.insert(old_key.to_string(), Value::Bool(*value));
            }
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct AppConfig {
    pub schema_version: u32,
    pub widgets: WidgetPreferences,
    /// Keep non-widget settings from the existing Python configuration intact during migration.
    #[serde(flatten)]
    pub legacy: BTreeMap<String, Value>,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self { schema_version: 1, widgets: WidgetPreferences::default(), legacy: BTreeMap::new() }
    }
}

impl AppConfig {
    pub fn load(path: &Path) -> io::Result<Self> {
        if !path.exists() { return Ok(Self::default()); }
        let contents = fs::read_to_string(path)?;
        let raw: Value = serde_json::from_str(&contents)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
        let has_canonical_enabled = raw
            .get("widgets")
            .and_then(|widgets| widgets.get("enabled"))
            .is_some();
        let mut config: Self = serde_json::from_value(raw)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;

        // A legacy Python config has flat `*_enabled` keys but no nested map.
        // Import those only in that case; otherwise canonical values win.
        if !has_canonical_enabled {
            for (old_key, new_key) in [
                ("clock_enabled", "clock"),
                ("system_enabled", "system"),
                ("tasks_enabled", "tasks"),
                ("weather_enabled", "weather"),
                ("cat_enabled", "cat"),
                ("media_enabled", "media"),
            ] {
                if let Some(value) = config.widgets.legacy.get(old_key).and_then(Value::as_bool) {
                    config.widgets.enabled.insert(new_key.to_string(), value);
                }
            }
        }
        config.widgets.normalize();
        Ok(config)
    }

    pub fn save_atomic(&self, path: &Path) -> io::Result<()> {
        let parent = path.parent()
            .filter(|p| !p.as_os_str().is_empty())
            .unwrap_or(Path::new("."));
        fs::create_dir_all(parent)?;
        let mut normalized = self.clone();
        normalized.widgets.normalize();
        let bytes = serde_json::to_vec_pretty(&normalized)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;

        let mut temporary = NamedTempFile::new_in(parent)?;
        temporary.write_all(&bytes)?;
        temporary.flush()?;
        temporary.as_file().sync_all()?;
        temporary.persist(path).map_err(|error| error.error)?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn widget_dimensions_and_refresh_are_bounded() {
        let mut settings = WidgetPreferences {
            rail_width: 1, card_height: u16::MAX, refresh_seconds: 0,
            ..WidgetPreferences::default()
        };
        settings.normalize();
        assert_eq!(settings.rail_width, 160);
        assert_eq!(settings.card_height, 260);
        assert_eq!(settings.refresh_seconds, 5);
    }

    #[test]
    fn widget_order_is_unique_complete_and_valid() {
        let mut settings = WidgetPreferences {
            left_order: vec!["clock".into(), "clock".into(), "unknown".into()],
            right_order: vec!["weather".into()],
            ..WidgetPreferences::default()
        };
        settings.normalize();
        let all: Vec<_> = settings.left_order.iter().chain(&settings.right_order).collect();
        assert_eq!(all.len(), WIDGETS.len());
        assert_eq!(all.iter().collect::<HashSet<_>>().len(), WIDGETS.len());
        assert!(all.iter().all(|name| WIDGETS.contains(&name.as_str())));
    }

    #[test]
    fn config_round_trips_atomically() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("config.json");
        let mut expected = AppConfig::default();
        expected.widgets.rail_width = 240;
        expected.save_atomic(&path).unwrap();
        assert_eq!(AppConfig::load(&path).unwrap(), expected);

        // Saving again must atomically replace the existing file on Windows.
        expected.widgets.enabled.insert("clock".into(), false);
        expected.widgets.card_height = 180;
        expected.save_atomic(&path).unwrap();
        assert_eq!(AppConfig::load(&path).unwrap(), expected);
    }

    #[test]
    fn malformed_config_is_reported_without_overwriting_it() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("config.json");
        fs::write(&path, "{broken").unwrap();
        assert_eq!(AppConfig::load(&path).unwrap_err().kind(), io::ErrorKind::InvalidData);
        assert_eq!(fs::read_to_string(path).unwrap(), "{broken");
    }

    #[test]
    fn legacy_python_settings_are_migrated_and_preserved() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("config.json");
        let legacy = r#"{
            "schema_version": 2,
            "general": {"hotkey": "Alt+Space"},
            "appearance": {"theme": "dark"},
            "widgets": {
                "clock_enabled": false,
                "system_enabled": true,
                "tasks_enabled": false,
                "weather_enabled": true,
                "cat_enabled": false,
                "media_enabled": true,
                "rail_width": 248,
                "card_height": 176,
                "left_order": ["tasks", "clock", "system"],
                "right_order": ["cat", "weather", "media"]
            }
        }"#;
        fs::write(&path, legacy).unwrap();

        let mut loaded = AppConfig::load(&path).unwrap();
        assert!(!loaded.widgets.enabled["clock"]);
        assert!(!loaded.widgets.enabled["tasks"]);
        assert!(loaded.widgets.enabled["media"]);
        assert_eq!(loaded.widgets.rail_width, 248);
        assert_eq!(loaded.widgets.card_height, 176);
        assert_eq!(loaded.widgets.left_order, vec!["tasks", "clock", "system"]);
        assert_eq!(loaded.schema_version, 2);

        loaded.widgets.enabled.insert("clock".into(), true);
        loaded.save_atomic(&path).unwrap();
        let saved: Value = serde_json::from_slice(&fs::read(&path).unwrap()).unwrap();
        assert_eq!(saved["general"]["hotkey"], "Alt+Space");
        assert_eq!(saved["appearance"]["theme"], "dark");
        assert_eq!(saved["widgets"]["clock_enabled"], true);
        assert_eq!(saved["widgets"]["enabled"]["clock"], true);
    }

    #[test]
    fn missing_config_uses_defaults() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("missing.json");
        assert_eq!(AppConfig::load(&path).unwrap(), AppConfig::default());
    }
}
