slint::include_modules!();

use std::rc::Rc;
use seekr_native::search::SearchEngine;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let window = AppWindow::new()?;
    let engine = Rc::new(SearchEngine::default());
    let weak_window = window.as_weak();

    window.on_search_changed(move |query| {
        let text = engine.search(query.as_str());
        if let Some(window) = weak_window.upgrade() {
            window.set_results_text(text.into());
        }
    });
    window.on_hide_requested(|| slint::quit_event_loop());

    window.run()?;
    Ok(())
}
