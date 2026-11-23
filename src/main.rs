slint::include_modules!();

use std::cell::RefCell;
use std::rc::Rc;
use std::sync::{Arc, Mutex};
use seekr_native::config::{config_path, AppConfig};
use seekr_native::search::{SearchEngine, SearchResult};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let window = AppWindow::new()?;
    // Build the Windows app/file indexes off the UI thread. Startup must stay
    // responsive even when user folders contain many files or slow locations.
    let engine: Arc<Mutex<Option<SearchEngine>>> = Arc::new(Mutex::new(None));
    let index_engine = Arc::clone(&engine);
    std::thread::Builder::new()
        .name("seekr-search-index".into())
        .spawn(move || {
            let indexed = SearchEngine::default();
            if let Ok(mut slot) = index_engine.lock() {
                *slot = Some(indexed);
            }
        })?;
    let last_results: Rc<RefCell<Vec<SearchResult>>> = Rc::new(RefCell::new(Vec::new()));
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
        window.set_rail_width_text(settings.widgets.rail_width.to_string().into());
        window.set_card_height_text(settings.widgets.card_height.to_string().into());
        window.set_left_order_text(settings.widgets.left_order.join(", ").into());
        window.set_right_order_text(settings.widgets.right_order.join(", ").into());
    }

    let weak_window = window.as_weak();
    let search_results = last_results.clone();
    let search_engine = Arc::clone(&engine);
    window.set_results_text("Indexing apps and files in the background…".into());
    window.on_search_changed(move |query| {
        let (found, indexing) = match search_engine.lock() {
            Ok(slot) => match slot.as_ref() {
                Some(engine) => (engine.search_results(query.as_str()), false),
                None => (Vec::new(), true),
            },
            Err(_) => (Vec::new(), true),
        };
        let text = if indexing {
            "Still indexing apps and files. Search will be available shortly.".to_owned()
        } else if query.trim().is_empty() {
            "Start typing to search.\n\nTry: an app name, a file name, or calc: 42 * 42".to_owned()
        } else if found.is_empty() {
            format!("No results for “{}”.", query.trim())
        } else {
            found.iter().map(|item| format!("{}\n{}  ·  {}", item.title, item.description, item.category)).collect::<Vec<_>>().join("\n\n")
        };
        *search_results.borrow_mut() = found;
        if let Some(window) = weak_window.upgrade() {
            window.set_results_text(text.into());
        }
    });

    let weak_window = window.as_weak();
    let launch_results = last_results.clone();
    window.on_launch_requested(move || {
        let result = launch_results.borrow().first().cloned();
        let message = match result {
            Some(item) => SearchEngine::launch(&item).map(|_| {
                if item.copy_text.is_some() {
                    format!("Copied {} to the clipboard.", item.title)
                } else {
                    format!("Opening {}…", item.title)
                }
            }),
            None => Err("Search for an application first.".into()),
        };
        if let Some(window) = weak_window.upgrade() {
            window.set_results_text(message.unwrap_or_else(|error| error).into());
        }
    });

    let weak_window = window.as_weak();
    let widget_config = config.clone();
    let config_path = path.clone();
    window.on_widget_toggled(move |name, enabled| {
        let mut settings = widget_config.borrow_mut();
        let key = name.to_string();
        if let Some(previous) = settings.widgets.enabled.get(&key).copied() {
            settings.widgets.enabled.insert(key.clone(), enabled);
            match settings.save_atomic(&config_path) {
                Ok(()) => {
                    if let Some(window) = weak_window.upgrade() {
                        window.set_results_text(format!("Saved widget preference: {name}.").into());
                    }
                }
                Err(error) => {
                    // Revert the in-memory change when persistence fails.
                    settings.widgets.enabled.insert(key, previous);
                    if let Some(window) = weak_window.upgrade() {
                        window.set_results_text(format!("Could not save settings: {error}").into());
                    }
                }
            }
        }
    });


    let weak_window = window.as_weak();
    let size_config = config.clone();
    let config_path = path.clone();
    window.on_widget_size_changed(move |name, value| {
        let parsed = value.trim().parse::<u16>();
        let mut settings = size_config.borrow_mut();
        let key = name.to_string();
        let Ok(parsed) = parsed else {
            if let Some(window) = weak_window.upgrade() {
                window.set_results_text("Enter a whole number for widget dimensions.".into());
            }
            return;
        };
        let previous = match key.as_str() {
            "rail_width" => settings.widgets.rail_width,
            "card_height" => settings.widgets.card_height,
            _ => return,
        };
        match key.as_str() {
            "rail_width" => settings.widgets.rail_width = parsed,
            "card_height" => settings.widgets.card_height = parsed,
            _ => return,
        }
        settings.widgets.normalize();
        match settings.save_atomic(&config_path) {
            Ok(()) => {
                if let Some(window) = weak_window.upgrade() {
                    window.set_rail_width_text(settings.widgets.rail_width.to_string().into());
                    window.set_card_height_text(settings.widgets.card_height.to_string().into());
                    window.set_results_text("Saved widget dimensions. Values are clamped to supported ranges.".into());
                }
            }
            Err(error) => {
                match key.as_str() {
                    "rail_width" => settings.widgets.rail_width = previous,
                    "card_height" => settings.widgets.card_height = previous,
                    _ => {}
                }
                if let Some(window) = weak_window.upgrade() {
                    window.set_results_text(format!("Could not save widget dimensions: {error}").into());
                }
            }
        }
    });


    let weak_window = window.as_weak();
    let order_config = config.clone();
    let order_config_path = path.clone();
    window.on_widget_order_changed(move |side, value| {
        let side = side.to_string();
        let requested: Vec<String> = value
            .split(',')
            .map(str::trim)
            .filter(|name| !name.is_empty())
            .map(str::to_lowercase)
            .collect();
        let mut settings = order_config.borrow_mut();
        let previous = match side.as_str() {
            "left" => settings.widgets.left_order.clone(),
            "right" => settings.widgets.right_order.clone(),
            _ => return,
        };
        match side.as_str() {
            "left" => settings.widgets.left_order = requested,
            "right" => settings.widgets.right_order = requested,
            _ => return,
        }
        settings.widgets.normalize();
        match settings.save_atomic(&order_config_path) {
            Ok(()) => {
                if let Some(window) = weak_window.upgrade() {
                    window.set_left_order_text(settings.widgets.left_order.join(", ").into());
                    window.set_right_order_text(settings.widgets.right_order.join(", ").into());
                    window.set_results_text("Saved widget order. Unknown or duplicate names were removed.".into());
                }
            }
            Err(error) => {
                match side.as_str() {
                    "left" => settings.widgets.left_order = previous,
                    "right" => settings.widgets.right_order = previous,
                    _ => {}
                }
                settings.widgets.normalize();
                if let Some(window) = weak_window.upgrade() {
                    window.set_left_order_text(settings.widgets.left_order.join(", ").into());
                    window.set_right_order_text(settings.widgets.right_order.join(", ").into());
                    window.set_results_text(format!("Could not save widget order: {error}").into());
                }
            }
        }
    });

    window.on_hide_requested(|| { let _ = slint::quit_event_loop(); });
    window.run()?;
    Ok(())
}
