slint::include_modules!();

use std::cell::RefCell;
use std::rc::Rc;
use seekr_native::config::{config_path, AppConfig};
use seekr_native::search::SearchEngine;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let window = AppWindow::new()?;
    let engine = Rc::new(SearchEngine::default());
    let path = config_path();
    let config = match AppConfig::load(&path) {
        Ok(config) => config,
        Err(error) => {
            eprintln!("Could not read SeekR settings at {}: {error}", path.display());
            // Do not overwrite malformed user settings on startup.
            AppConfig::default()
        }
    };
    let config = Rc::new(RefCell::new(config));

    {
        let settings = config.borrow();
        window.set_clock_enabled(*settings.widgets.enabled.get("clock").unwrap_or(&true));
        window.set_system_enabled(*settings.widgets.enabled.get("system").unwrap_or(&true));
        window.set_tasks_enabled(*settings.widgets.enabled.get("tasks").unwrap_or(&true));
        window.set_weather_enabled(*settings.widgets.enabled.get("weather").unwrap_or(&true));
        window.set_cat_enabled(*settings.widgets.enabled.get("cat").unwrap_or(&true));
        window.set_media_enabled(*settings.widgets.enabled.get("media").unwrap_or(&false));
    }

    let weak_window = window.as_weak();
    window.on_search_changed(move |query| {
        let text = engine.search(query.as_str());
        if let Some(window) = weak_window.upgrade() {
            window.set_results_text(text.into());
        }
    });

    let weak_window = window.as_weak();
    let config_path = path.clone();
    window.on_widget_toggled(move |name, enabled| {
        let mut settings = config.borrow_mut();
        if let Some(value) = settings.widgets.enabled.get_mut(name.as_str()) {
            *value = enabled;
            match settings.save_atomic(&config_path) {
                Ok(()) => {
                    if let Some(window) = weak_window.upgrade() {
                        window.set_results_text(format!("Saved widget preference: {name}.").into());
                    }
                }
                Err(error) => {
                    // Revert the in-memory change when persistence fails.
                    *value = !enabled;
                    if let Some(window) = weak_window.upgrade() {
                        window.set_results_text(format!("Could not save settings: {error}").into());
                    }
                }
            }
        }
    });

    window.on_hide_requested(|| { let _ = slint::quit_event_loop(); });
    window.run()?;
    Ok(())
}
