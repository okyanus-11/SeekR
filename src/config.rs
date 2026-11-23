use serde::{Deserialize, Serialize};
use std::collections::{BTreeMap, HashSet};
use std::fs;
use std::io::{self, Write};
use std::path::Path;
use tempfile::NamedTempFile;

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
        }
    }
}

impl WidgetPreferences {
    pub fn normalize(&mut self) {
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
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(default)]
pub struct AppConfig {
    pub schema_version: u32,
    pub widgets: WidgetPreferences,
}

impl Default for AppConfig {
    fn default() -> Self {
        Self { schema_version: 1, widgets: WidgetPreferences::default() }
    }
}

impl AppConfig {
    pub fn load(path: &Path) -> io::Result<Self> {
        if !path.exists() { return Ok(Self::default()); }
        let contents = fs::read_to_string(path)?;
        let mut config: Self = serde_json::from_str(&contents)
            .map_err(|error| io::Error::new(io::ErrorKind::InvalidData, error))?;
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
    fn missing_config_uses_defaults() {
        let directory = tempfile::tempdir().unwrap();
        let path = directory.path().join("missing.json");
        assert_eq!(AppConfig::load(&path).unwrap(), AppConfig::default());
    }
}
