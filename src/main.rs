slint::include_modules!();

use std::cell::{Cell, RefCell};
use std::rc::Rc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, mpsc};
use std::time::Duration;

use seekr_native::config::{AppConfig, config_path};
use seekr_native::platform;
use seekr_native::search::{SearchEngine, SearchResult};
use slint::{ModelRc, VecModel};

/// Wait this long after the last keystroke before running a query.
const DEBOUNCE: Duration = Duration::from_millis(70);
/// How often the UI thread drains results produced by the search worker.
const POLL_INTERVAL: Duration = Duration::from_millis(15);

struct Request {
    generation: u64,
    query: String,
}

enum WorkerMessage {
    Ready {
        applications: usize,
        files: usize,
    },
    Results {
        generation: u64,
        results: Vec<SearchResult>,
    },
}

fn to_item(result: &SearchResult) -> ResultItem {
    ResultItem {
        title: result.title.clone().into(),
        description: result.description.clone().into(),
        category: result.category.clone().into(),
        action: result.action_label().into(),
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // A second launch activates the running window instead of opening a
    // second copy.
    if !platform::ensure_single_instance("SeekR") {
        return Ok(());
    }

    let window = AppWindow::new()?;

    // ---- Search worker -----------------------------------------------------
    // Building the Start Menu / user-folder indexes is I/O heavy, so the engine
    // lives on a worker thread. The UI thread only sends queries and drains
    // results; it never scans the filesystem or waits on a lock.
    let (request_tx, request_rx) = mpsc::channel::<Request>();
    let (response_tx, response_rx) = mpsc::channel::<WorkerMessage>();
    std::thread::Builder::new()
        .name("seekr-search".into())
        .spawn(move || {
            let engine = SearchEngine::default();
            let (applications, files) = engine.index_counts();
            if response_tx
                .send(WorkerMessage::Ready {
                    applications,
                    files,
                })
                .is_err()
            {
                return;
            }
            while let Ok(request) = request_rx.recv() {
                let results = engine.search_results(&request.query);
                let message = WorkerMessage::Results {
                    generation: request.generation,
                    results,
                };
                if response_tx.send(message).is_err() {
                    break;
                }
            }
        })?;

    let model = Rc::new(VecModel::from(Vec::<ResultItem>::new()));
    window.set_results(ModelRc::from(model.clone()));

    let snapshot: Rc<RefCell<Vec<SearchResult>>> = Rc::new(RefCell::new(Vec::new()));
    let selected = Rc::new(Cell::new(0usize));
    let generation = Rc::new(Cell::new(0u64));
    let pending_query = Rc::new(RefCell::new(String::new()));

    // ---- Configuration -----------------------------------------------------
    let path = config_path();
    let config = match AppConfig::load(&path) {
        Ok(config) => config,
        Err(error) => {
            eprintln!(
                "Could not read SeekR settings at {}: {error}",
                path.display()
            );
            // Never overwrite malformed user settings on startup.
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

    // ---- Clock -------------------------------------------------------------
    window.set_clock_time(chrono::Local::now().format("%H:%M:%S").to_string().into());
    let clock_timer = slint::Timer::default();
    let clock_window = window.as_weak();
    clock_timer.start(
        slint::TimerMode::Repeated,
        Duration::from_secs(1),
        move || {
            if let Some(window) = clock_window.upgrade() {
                window.set_clock_time(chrono::Local::now().format("%H:%M:%S").to_string().into());
            }
        },
    );

    // ---- Debounced search requests ----------------------------------------
    let debounce = Rc::new(slint::Timer::default());
    {
        let debounce = debounce.clone();
        let pending = pending_query.clone();
        let generation = generation.clone();
        let requests = request_tx.clone();
        let weak = window.as_weak();
        window.on_search_changed(move |query| {
            // Every keystroke advances the generation so any result produced
            // for an older query can never replace the current list.
            let request_generation = generation.get() + 1;
            generation.set(request_generation);
            *pending.borrow_mut() = query.to_string();
            if let Some(window) = weak.upgrade() {
                window.set_status_text("Searching…".into());
            }
            let pending = pending.clone();
            let requests = requests.clone();
            debounce.start(slint::TimerMode::SingleShot, DEBOUNCE, move || {
                let query = pending.borrow().clone();
                let _ = requests.send(Request {
                    generation: request_generation,
                    query,
                });
            });
        });
    }

    // ---- Result pump -------------------------------------------------------
    let poll_timer = slint::Timer::default();
    {
        let model = model.clone();
        let snapshot = snapshot.clone();
        let selected = selected.clone();
        let generation = generation.clone();
        let weak = window.as_weak();
        poll_timer.start(slint::TimerMode::Repeated, POLL_INTERVAL, move || {
            let Some(window) = weak.upgrade() else {
                return;
            };
            while let Ok(message) = response_rx.try_recv() {
                match message {
                    WorkerMessage::Ready {
                        applications,
                        files,
                    } => {
                        window.set_status_text(
                            format!("Indexed {applications} apps · {files} files").into(),
                        );
                    }
                    WorkerMessage::Results {
                        generation: result_generation,
                        results,
                    } => {
                        if result_generation != generation.get() {
                            // Stale: a newer query has already been issued.
                            continue;
                        }
                        let items: Vec<ResultItem> = results.iter().map(to_item).collect();
                        let count = items.len();
                        model.set_vec(items);
                        *snapshot.borrow_mut() = results;
                        selected.set(0);
                        window.set_selected_index(0);
                        window.set_status_text(
                            if count == 0 {
                                "No results".to_owned()
                            } else {
                                format!("{count} result{}", if count == 1 { "" } else { "s" })
                            }
                            .into(),
                        );
                    }
                }
            }
        });
    }

    // ---- Selection and activation -----------------------------------------
    {
        let snapshot = snapshot.clone();
        let selected = selected.clone();
        let weak = window.as_weak();
        window.on_selection_moved(move |delta| {
            let length = snapshot.borrow().len();
            if length == 0 {
                return;
            }
            let next = ((selected.get() as i32 + delta).rem_euclid(length as i32)) as usize;
            selected.set(next);
            if let Some(window) = weak.upgrade() {
                window.set_selected_index(next as i32);
            }
        });
    }

    {
        let snapshot = snapshot.clone();
        let weak = window.as_weak();
        window.on_activated(move |index| {
            let Some(window) = weak.upgrade() else {
                return;
            };
            if index < 0 {
                return;
            }
            let result = snapshot.borrow().get(index as usize).cloned();
            let Some(result) = result else {
                window.set_status_text("Search for something first.".into());
                return;
            };
            match SearchEngine::launch(&result) {
                Ok(()) => {
                    if result.target.is_some() {
                        // Launching is the end of this launcher interaction.
                        window.set_search_text("".into());
                        let _ = window.hide();
                    } else {
                        window.set_status_text(format!("Copied “{}”.", result.title).into());
                    }
                }
                Err(error) => window.set_status_text(error.into()),
            }
        });
    }

    {
        let model = model.clone();
        let snapshot = snapshot.clone();
        let selected = selected.clone();
        let generation = generation.clone();
        let pending_query = pending_query.clone();
        let weak = window.as_weak();
        window.on_clear_requested(move || {
            generation.set(generation.get() + 1);
            pending_query.borrow_mut().clear();
            snapshot.borrow_mut().clear();
            model.set_vec(Vec::new());
            selected.set(0);
            if let Some(window) = weak.upgrade() {
                window.set_selected_index(0);
                window.set_status_text("Search cleared".into());
            }
        });
    }

    window.on_close_requested(|| {
        let _ = slint::quit_event_loop();
    });

    // ---- Widget preferences ------------------------------------------------
    {
        let weak = window.as_weak();
        let widget_config = config.clone();
        let config_path = path.clone();
        window.on_widget_toggled(move |name, enabled| {
            let mut settings = widget_config.borrow_mut();
            let key = name.to_string();
            let Some(previous) = settings.widgets.enabled.get(&key).copied() else {
                return;
            };
            settings.widgets.enabled.insert(key.clone(), enabled);
            match settings.save_atomic(&config_path) {
                Ok(()) => {
                    if let Some(window) = weak.upgrade() {
                        window.set_status_text(format!("Saved widget preference: {name}").into());
                    }
                }
                Err(error) => {
                    // Revert the in-memory change when persistence fails.
                    settings.widgets.enabled.insert(key, previous);
                    if let Some(window) = weak.upgrade() {
                        window.set_status_text(format!("Could not save settings: {error}").into());
                    }
                }
            }
        });
    }

    {
        let weak = window.as_weak();
        let size_config = config.clone();
        let config_path = path.clone();
        window.on_widget_size_changed(move |name, value| {
            let parsed = value.trim().parse::<u16>();
            let mut settings = size_config.borrow_mut();
            let key = name.to_string();
            let Ok(parsed) = parsed else {
                if let Some(window) = weak.upgrade() {
                    window.set_status_text("Enter a whole number for widget dimensions.".into());
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
                    if let Some(window) = weak.upgrade() {
                        window.set_rail_width_text(settings.widgets.rail_width.to_string().into());
                        window
                            .set_card_height_text(settings.widgets.card_height.to_string().into());
                        window.set_status_text(
                            "Saved widget dimensions (clamped to supported ranges).".into(),
                        );
                    }
                }
                Err(error) => {
                    match key.as_str() {
                        "rail_width" => settings.widgets.rail_width = previous,
                        "card_height" => settings.widgets.card_height = previous,
                        _ => {}
                    }
                    if let Some(window) = weak.upgrade() {
                        window.set_status_text(
                            format!("Could not save widget dimensions: {error}").into(),
                        );
                    }
                }
            }
        });
    }

    {
        let weak = window.as_weak();
        let order_config = config.clone();
        let config_path = path.clone();
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
            match settings.save_atomic(&config_path) {
                Ok(()) => {
                    if let Some(window) = weak.upgrade() {
                        window.set_left_order_text(settings.widgets.left_order.join(", ").into());
                        window.set_right_order_text(settings.widgets.right_order.join(", ").into());
                        window.set_status_text(
                            "Saved widget order (unknown or duplicate names removed).".into(),
                        );
                    }
                }
                Err(error) => {
                    match side.as_str() {
                        "left" => settings.widgets.left_order = previous,
                        "right" => settings.widgets.right_order = previous,
                        _ => {}
                    }
                    settings.widgets.normalize();
                    if let Some(window) = weak.upgrade() {
                        window.set_left_order_text(settings.widgets.left_order.join(", ").into());
                        window.set_right_order_text(settings.widgets.right_order.join(", ").into());
                        window.set_status_text(
                            format!("Could not save widget order: {error}").into(),
                        );
                    }
                }
            }
        });
    }

    // ---- Global hotkey -----------------------------------------------------
    // The hotkey thread only raises a flag; the UI thread performs the actual
    // show so Slint is never touched from a foreign thread.
    let summoned = Arc::new(AtomicBool::new(false));
    {
        let summoned = summoned.clone();
        platform::spawn_hotkey(move || summoned.store(true, Ordering::SeqCst));
    }
    let summon_timer = slint::Timer::default();
    {
        let summoned = summoned.clone();
        let weak = window.as_weak();
        summon_timer.start(
            slint::TimerMode::Repeated,
            Duration::from_millis(120),
            move || {
                if !summoned.swap(false, Ordering::SeqCst) {
                    return;
                }
                if let Some(window) = weak.upgrade() {
                    let _ = window.show();
                }
            },
        );
    }

    window.run()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn items_expose_their_action_label() {
        let copyable = SearchResult {
            title: "42".into(),
            description: "answer".into(),
            category: "Calculator".into(),
            score: 1.0,
            target: None,
            copy_text: Some("42".into()),
        };
        assert_eq!(to_item(&copyable).action.as_str(), "Copy");

        let launchable = SearchResult {
            target: Some(std::path::PathBuf::from("/tmp/x")),
            copy_text: None,
            ..copyable
        };
        assert_eq!(to_item(&launchable).action.as_str(), "Open");
    }
}
