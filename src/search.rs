use std::panic::{catch_unwind, AssertUnwindSafe};
use std::path::PathBuf;
use std::process::Command;

#[derive(Debug, Clone, PartialEq)]
pub struct SearchResult {
    pub title: String,
    pub description: String,
    pub category: String,
    pub score: f32,
    pub target: Option<PathBuf>,
    pub copy_text: Option<String>,
}

pub trait SearchProvider {
    fn id(&self) -> &'static str;
    fn search(&self, query: &str) -> Result<Vec<SearchResult>, String>;
}

pub struct SearchEngine {
    providers: Vec<Box<dyn SearchProvider>>,
}

impl SearchEngine {
    pub fn new() -> Self {
        Self {
            providers: vec![
                Box::new(BuiltInProvider),
                Box::new(WindowsAppsProvider::new()),
                Box::new(WindowsFilesProvider::new()),
            ],
        }
    }

    pub fn register(&mut self, provider: Box<dyn SearchProvider>) {
        self.providers.retain(|existing| existing.id() != provider.id());
        self.providers.push(provider);
    }

    pub fn search_results(&self, query: &str) -> Vec<SearchResult> {
        let query = query.trim();
        if query.is_empty() {
            return Vec::new();
        }

        let mut results = Vec::new();
        for provider in &self.providers {
            match catch_unwind(AssertUnwindSafe(|| provider.search(query))) {
                Ok(Ok(mut found)) => results.append(&mut found),
                Ok(Err(message)) => results.push(SearchResult {
                    title: format!("{} provider unavailable", provider.id()),
                    description: message,
                    category: "Status".into(),
                    score: 0.0,
                    target: None,
                    copy_text: None,
                }),
                Err(_) => results.push(SearchResult {
                    title: format!("{} provider failed safely", provider.id()),
                    description: "A provider panicked; other providers remain available.".into(),
                    category: "Status".into(),
                    score: 0.0,
                    target: None,
                    copy_text: None,
                }),
            }
        }

        results.sort_by(|a, b| {
            b.score
                .total_cmp(&a.score)
                .then_with(|| a.title.to_lowercase().cmp(&b.title.to_lowercase()))
        });
        results.truncate(12);
        results
    }

    pub fn search(&self, query: &str) -> String {
        let query = query.trim();
        if query.is_empty() {
            return "Start typing to search.\n\nTry: calc: 2 + 2, discord, invoice".into();
        }
        let results = self.search_results(query);
        if results.is_empty() {
            return format!("No results for “{query}”.");
        }
        results
            .into_iter()
            .map(|item| format!("{}\n{}  ·  {}", item.title, item.description, item.category))
            .collect::<Vec<_>>()
            .join("\n\n")
    }

    pub fn launch(result: &SearchResult) -> Result<(), String> {
        if let Some(text) = result.copy_text.as_ref() {
            let mut clipboard = arboard::Clipboard::new()
                .map_err(|error| format!("Could not access the clipboard: {error}"))?;
            return clipboard
                .set_text(text.clone())
                .map_err(|error| format!("Could not copy the result: {error}"));
        }

        let Some(path) = result.target.as_ref() else {
            return Err("This result does not have a launch action.".into());
        };
        if !path.exists() {
            return Err(format!("The item no longer exists: {}", path.display()));
        }

        #[cfg(target_os = "windows")]
        let outcome = Command::new("explorer.exe").arg(path).spawn();
        #[cfg(not(target_os = "windows"))]
        let outcome = Command::new("xdg-open").arg(path).spawn();

        outcome
            .map(|_| ())
            .map_err(|error| format!("Could not open {}: {error}", path.display()))
    }
}

impl Default for SearchEngine {
    fn default() -> Self {
        Self::new()
    }
}

struct BuiltInProvider;

impl SearchProvider for BuiltInProvider {
    fn id(&self) -> &'static str {
        "built-in"
    }

    fn search(&self, query: &str) -> Result<Vec<SearchResult>, String> {
        if let Some(expression) = query.strip_prefix("calc:") {
            let expression = expression.trim();
            if expression.is_empty() {
                return Ok(Vec::new());
            }
            return match meval::eval_str(expression) {
                Ok(value) if value.is_finite() => {
                    let answer = value.to_string();
                    Ok(vec![SearchResult {
                        title: answer.clone(),
                        description: format!("Result of {expression} · activate to copy"),
                        category: "Calculator".into(),
                        score: 1.0,
                        target: None,
                        copy_text: Some(answer),
                    }])
                }
                Ok(_) => Ok(vec![SearchResult {
                    title: "Result is not finite".into(),
                    description: "Try a different expression.".into(),
                    category: "Calculator".into(),
                    score: 0.0,
                    target: None,
                    copy_text: None,
                }]),
                Err(error) => Ok(vec![SearchResult {
                    title: "Invalid expression".into(),
                    description: error.to_string(),
                    category: "Calculator".into(),
                    score: 0.0,
                    target: None,
                    copy_text: None,
                }]),
            };
        }

        // Do not advertise placeholder tools that have no working action.
        Ok(Vec::new())
    }
}

/// A small cached index of the Windows Start Menu. Scanning happens once at
/// startup rather than on every keystroke.
struct WindowsAppsProvider {
    entries: Vec<(String, PathBuf)>,
}

impl WindowsAppsProvider {
    fn new() -> Self {
        let mut entries = Vec::new();
        #[cfg(target_os = "windows")]
        {
            let roots = [
                std::env::var_os("APPDATA").map(|value| {
                    PathBuf::from(value)
                        .join("Microsoft")
                        .join("Windows")
                        .join("Start Menu")
                        .join("Programs")
                }),
                std::env::var_os("PROGRAMDATA").map(|value| {
                    PathBuf::from(value)
                        .join("Microsoft")
                        .join("Windows")
                        .join("Start Menu")
                        .join("Programs")
                }),
            ];
            for root in roots.into_iter().flatten() {
                collect_shortcuts(&root, 0, &mut entries);
            }
            entries.sort_by_key(|entry| entry.0.to_lowercase());
            entries.dedup_by(|a, b| a.1 == b.1);
        }
        Self { entries }
    }
}

impl SearchProvider for WindowsAppsProvider {
    fn id(&self) -> &'static str {
        "windows-apps"
    }

    fn search(&self, query: &str) -> Result<Vec<SearchResult>, String> {
        Ok(self
            .entries
            .iter()
            .filter_map(|(name, path)| {
                let score = match_score(query, name, "");
                (score > 0.0).then(|| SearchResult {
                    title: name.clone(),
                    description: "Open installed application".into(),
                    category: "Application".into(),
                    score: score + 0.03,
                    target: Some(path.clone()),
                    copy_text: None,
                })
            })
            .collect())
    }
}

#[cfg(target_os = "windows")]
fn collect_shortcuts(
    directory: &std::path::Path,
    depth: usize,
    output: &mut Vec<(String, PathBuf)>,
) {
    if depth > 4 {
        return;
    }
    let Ok(entries) = std::fs::read_dir(directory) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect_shortcuts(&path, depth + 1, output);
            continue;
        }
        let extension = path
            .extension()
            .and_then(|value| value.to_str())
            .unwrap_or_default();
        if !["lnk", "url", "exe"]
            .iter()
            .any(|candidate| extension.eq_ignore_ascii_case(candidate))
        {
            continue;
        }
        let Some(name) = path.file_stem().and_then(|value| value.to_str()) else {
            continue;
        };
        if !name.is_empty() {
            output.push((name.to_owned(), path));
        }
    }
}

/// A bounded index of common user folders. Only names and paths are read;
/// file contents are never inspected. The scan is shallow and capped.
struct WindowsFilesProvider {
    entries: Vec<(String, PathBuf)>,
}

impl WindowsFilesProvider {
    fn new() -> Self {
        let mut entries = Vec::new();
        #[cfg(target_os = "windows")]
        {
            if let Some(profile) = std::env::var_os("USERPROFILE").map(PathBuf::from) {
                for folder in ["Desktop", "Documents", "Downloads"] {
                    collect_user_files(&profile.join(folder), 0, &mut entries, 3000);
                    if entries.len() >= 3000 {
                        break;
                    }
                }
            }
        }
        entries.sort_by_key(|entry| entry.0.to_lowercase());
        entries.dedup_by(|a, b| a.1 == b.1);
        Self { entries }
    }
}

impl SearchProvider for WindowsFilesProvider {
    fn id(&self) -> &'static str {
        "windows-files"
    }

    fn search(&self, query: &str) -> Result<Vec<SearchResult>, String> {
        Ok(self
            .entries
            .iter()
            .filter_map(|(name, path)| {
                let score = match_score(query, name, "");
                (score > 0.0).then(|| SearchResult {
                    title: name.clone(),
                    description: path
                        .parent()
                        .map(|parent| parent.display().to_string())
                        .unwrap_or_default(),
                    category: if path.is_dir() { "Folder" } else { "File" }.into(),
                    score: score * 0.96,
                    target: Some(path.clone()),
                    copy_text: None,
                })
            })
            .collect())
    }
}

#[cfg(target_os = "windows")]
fn collect_user_files(
    directory: &std::path::Path,
    depth: usize,
    output: &mut Vec<(String, PathBuf)>,
    limit: usize,
) {
    if depth > 2 || output.len() >= limit {
        return;
    }
    let Ok(entries) = std::fs::read_dir(directory) else {
        return;
    };
    for entry in entries.flatten() {
        if output.len() >= limit {
            break;
        }
        let Ok(file_type) = entry.file_type() else {
            continue;
        };
        if file_type.is_symlink() {
            continue;
        }
        let path = entry.path();
        let Some(name) = path.file_name().and_then(|value| value.to_str()) else {
            continue;
        };
        if name.starts_with('.') || name.starts_with('$') {
            continue;
        }
        if file_type.is_dir() {
            output.push((name.to_owned(), path.clone()));
            if depth < 2 {
                collect_user_files(&path, depth + 1, output, limit);
            }
        } else if file_type.is_file() {
            output.push((name.to_owned(), path));
        }
    }
}

#[cfg(not(target_os = "windows"))]
fn collect_user_files(
    _: &std::path::Path,
    _: usize,
    _: &mut Vec<(String, PathBuf)>,
    _: usize,
) {
}

fn match_score(query: &str, title: &str, description: &str) -> f32 {
    let query = query.to_lowercase();
    let title = title.to_lowercase();
    let description = description.to_lowercase();
    if query.is_empty() {
        return 0.0;
    }
    if title == query {
        return 1.0;
    }
    if title.starts_with(&query) {
        return 0.92;
    }
    if title.contains(&query) {
        return 0.82;
    }
    if description.contains(&query) {
        return 0.62;
    }

    let title_words: Vec<&str> = title.split_whitespace().collect();
    let query_words: Vec<&str> = query.split_whitespace().collect();
    if query_words.is_empty() || title_words.is_empty() {
        return 0.0;
    }

    let mut total = 0.0;
    for query_word in &query_words {
        let best = title_words
            .iter()
            .map(|word| edit_distance(query_word, word))
            .min()
            .unwrap_or(usize::MAX);
        let allowance = (query_word.chars().count() / 3).max(1);
        if best > allowance {
            return 0.0;
        }
        total += 0.72 - (best as f32 * 0.08);
    }
    total / query_words.len() as f32
}

fn edit_distance(left: &str, right: &str) -> usize {
    let left: Vec<char> = left.chars().collect();
    let right: Vec<char> = right.chars().collect();
    let mut previous: Vec<usize> = (0..=right.len()).collect();
    let mut current = vec![0; right.len() + 1];

    for (row, left_char) in left.iter().enumerate() {
        current[0] = row + 1;
        for (column, right_char) in right.iter().enumerate() {
            let substitution = previous[column] + usize::from(left_char != right_char);
            let insertion = current[column] + 1;
            let deletion = previous[column + 1] + 1;
            current[column + 1] = substitution.min(insertion).min(deletion);
        }
        std::mem::swap(&mut previous, &mut current);
    }
    previous[right.len()]
}

#[cfg(test)]
mod tests {
    use super::*;

    struct FailingProvider;

    impl SearchProvider for FailingProvider {
        fn id(&self) -> &'static str {
            "failing"
        }

        fn search(&self, _: &str) -> Result<Vec<SearchResult>, String> {
            Err("test failure".into())
        }
    }

    struct PanickingProvider;

    impl SearchProvider for PanickingProvider {
        fn id(&self) -> &'static str {
            "panicking"
        }

        fn search(&self, _: &str) -> Result<Vec<SearchResult>, String> {
            panic!("simulated provider panic");
        }
    }

    #[test]
    fn exact_matches_rank_above_prefix_and_substring() {
        assert!(SearchEngine::default().search("settings").starts_with("No results"));
    }

    #[test]
    fn matching_is_case_insensitive_and_typo_tolerant() {
        let engine = SearchEngine::default();
        assert!(engine.search("CALC").contains("Calculator"));
        assert!(engine.search("clculator").contains("Calculator"));
    }

    #[test]
    fn calculator_evaluates_and_returns_copyable_result() {
        let results = SearchEngine::default().search_results("calc: sqrt(81) + 3");
        assert_eq!(results[0].title, "12");
        assert_eq!(results[0].copy_text.as_deref(), Some("12"));
    }

    #[test]
    fn calculator_rejects_invalid_and_non_finite_expressions() {
        let engine = SearchEngine::default();
        assert!(engine.search("calc: 1 / 0").contains("not finite"));
        assert!(engine.search("calc: (").contains("Invalid expression"));
    }

    #[test]
    fn empty_query_returns_guidance() {
        assert!(SearchEngine::default().search("  ").contains("Start typing"));
    }

    #[test]
    fn unknown_query_returns_empty_state() {
        assert!(SearchEngine::default().search("not-a-real-feature").contains("No results"));
    }

    #[test]
    fn provider_errors_do_not_abort_search() {
        let mut engine = SearchEngine::default();
        engine.register(Box::new(FailingProvider));
        let output = engine.search("settings");
        assert!(output.contains("provider unavailable"));
    }

    #[test]
    fn provider_panics_are_contained() {
        let mut engine = SearchEngine::default();
        engine.register(Box::new(PanickingProvider));
        let output = engine.search("settings");
        assert!(output.contains("failed safely"));
    }

    #[test]
    fn registering_same_provider_replaces_it() {
        let mut engine = SearchEngine::default();
        engine.register(Box::new(FailingProvider));
        engine.register(Box::new(FailingProvider));
        assert_eq!(
            engine
                .providers
                .iter()
                .filter(|provider| provider.id() == "failing")
                .count(),
            1
        );
    }

    #[test]
    fn unrelated_query_does_not_match_generic_description() {
        assert_eq!(match_score("xyz", "Calculator", ""), 0.0);
    }

    #[test]
    fn typo_matching_requires_a_close_title_token() {
        assert!(match_score("clculator", "Calculator", "") > 0.0);
        assert_eq!(match_score("calculator xyz", "Calculator", ""), 0.0);
    }

    #[test]
    fn result_launch_without_target_is_rejected() {
        let result = SearchResult {
            title: "Settings".into(),
            description: "Configure SeekR".into(),
            category: "Application".into(),
            score: 1.0,
            target: None,
            copy_text: None,
        };
        assert!(SearchEngine::launch(&result).is_err());
    }
}
