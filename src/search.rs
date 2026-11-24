use std::collections::HashSet;
use std::panic::{AssertUnwindSafe, catch_unwind};
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

impl SearchResult {
    /// Human label for the action the row performs when activated.
    pub fn action_label(&self) -> &'static str {
        if self.copy_text.is_some() {
            "Copy"
        } else if self.target.is_some() {
            "Open"
        } else {
            ""
        }
    }

    pub fn status(title: impl Into<String>, description: impl Into<String>) -> Self {
        Self {
            title: title.into(),
            description: description.into(),
            category: "Status".into(),
            score: 0.0,
            target: None,
            copy_text: None,
        }
    }
}

pub trait SearchProvider: Send + Sync {
    fn id(&self) -> &'static str;
    fn search(&self, query: &str) -> Result<Vec<SearchResult>, String>;
    /// Number of prepared entries in this provider's index. Used for the
    /// status line so the user can see when indexing finished.
    fn index_size(&self) -> usize {
        0
    }
}

/// Explicit search modes. Plain text uses [`QueryKind::Auto`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum QueryKind {
    Auto,
    Apps,
    Files,
    Calc,
    Time,
}

#[derive(Debug, Clone, PartialEq)]
pub struct ParsedQuery {
    pub kind: QueryKind,
    pub term: String,
}

/// Parse `prefix:term`. Unknown prefixes (and anything that looks like a
/// scheme or path, such as `http://…` or `C:\…`) stay in the plain query.
pub fn parse_query(raw: &str) -> ParsedQuery {
    let trimmed = raw.trim();
    let Some(index) = trimmed.find(':') else {
        return ParsedQuery {
            kind: QueryKind::Auto,
            term: trimmed.to_string(),
        };
    };
    let prefix = &trimmed[..index];
    // Windows paths and URLs contain ':' followed by separators; only treat
    // short alphabetic words as a prefix.
    if prefix.is_empty() || prefix.len() > 10 || !prefix.chars().all(|c| c.is_ascii_alphabetic()) {
        return ParsedQuery {
            kind: QueryKind::Auto,
            term: trimmed.to_string(),
        };
    }
    let kind = match prefix.to_ascii_lowercase().as_str() {
        "app" | "apps" => QueryKind::Apps,
        "file" | "files" => QueryKind::Files,
        "calc" | "=" => QueryKind::Calc,
        "time" => QueryKind::Time,
        _ => {
            return ParsedQuery {
                kind: QueryKind::Auto,
                term: trimmed.to_string(),
            };
        }
    };
    ParsedQuery {
        kind,
        term: trimmed[index + 1..].trim().to_string(),
    }
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
        self.providers
            .retain(|existing| existing.id() != provider.id());
        self.providers.push(provider);
    }

    /// (applications, files) currently indexed.
    pub fn index_counts(&self) -> (usize, usize) {
        let mut apps = 0;
        let mut files = 0;
        for provider in &self.providers {
            match provider.id() {
                "windows-apps" => apps += provider.index_size(),
                "windows-files" => files += provider.index_size(),
                _ => {}
            }
        }
        (apps, files)
    }

    pub fn search_results(&self, raw: &str) -> Vec<SearchResult> {
        let parsed = parse_query(raw);
        let mut results = Vec::new();

        match parsed.kind {
            QueryKind::Calc => results.extend(calculator(&parsed.term)),
            QueryKind::Time => results.push(local_time()),
            QueryKind::Auto | QueryKind::Apps | QueryKind::Files => {
                if parsed.term.is_empty() {
                    return Vec::new();
                }
                if parsed.kind == QueryKind::Auto {
                    results.extend(auto_calculator(&parsed.term));
                }
                for provider in &self.providers {
                    match catch_unwind(AssertUnwindSafe(|| provider.search(&parsed.term))) {
                        Ok(Ok(mut found)) => results.append(&mut found),
                        Ok(Err(message)) => results.push(SearchResult::status(
                            format!("{} provider unavailable", provider.id()),
                            message,
                        )),
                        Err(_) => results.push(SearchResult::status(
                            format!("{} provider failed safely", provider.id()),
                            "A provider panicked; other providers remain available.",
                        )),
                    }
                }
            }
        }

        // Explicit prefixes narrow the source of results after every
        // provider has run, so third-party providers keep working.
        match parsed.kind {
            QueryKind::Apps => {
                results.retain(|item| matches!(item.category.as_str(), "Application" | "Status"))
            }
            QueryKind::Files => results
                .retain(|item| matches!(item.category.as_str(), "File" | "Folder" | "Status")),
            _ => {}
        }

        // Deterministic ordering: score first, then case-insensitive title.
        results.sort_by(|a, b| {
            b.score
                .total_cmp(&a.score)
                .then_with(|| a.title.to_lowercase().cmp(&b.title.to_lowercase()))
                .then_with(|| a.category.cmp(&b.category))
        });
        // Drop duplicates that point at the same target with the same title.
        let mut seen = HashSet::new();
        results.retain(|item| seen.insert((item.title.to_lowercase(), item.target.clone())));
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

        // Explorer resolves shortcuts (.lnk/.url), folders and documents the
        // same way the shell does, which a bare `spawn` of the path would not.
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

fn calculator(expression: &str) -> Vec<SearchResult> {
    let expression = expression.trim();
    if expression.is_empty() {
        return Vec::new();
    }
    match meval::eval_str(expression) {
        Ok(value) if value.is_finite() => {
            let answer = format_number(value);
            vec![SearchResult {
                title: answer.clone(),
                description: format!("Result of {expression} · activate to copy"),
                category: "Calculator".into(),
                score: 1.0,
                target: None,
                copy_text: Some(answer),
            }]
        }
        Ok(_) => vec![SearchResult::status(
            "Result is not finite",
            "Try a different expression.",
        )],
        Err(error) => vec![SearchResult::status(
            "Invalid expression",
            error.to_string(),
        )],
    }
}

/// Recognize a plain arithmetic expression ("2+2", "15% of 80" is not
/// supported) so users get the answer without typing `calc:`.
fn auto_calculator(term: &str) -> Vec<SearchResult> {
    let has_operator = term
        .chars()
        .any(|c| matches!(c, '+' | '-' | '*' | '/' | '^' | '%'));
    let has_digit = term.chars().any(|c| c.is_ascii_digit());
    let only_math = term.chars().all(|c| {
        c.is_ascii_digit() || matches!(c, '+' | '-' | '*' | '/' | '^' | '%' | '.' | '(' | ')' | ' ')
    });
    if !(has_operator && has_digit && only_math) {
        return Vec::new();
    }
    calculator(term)
}

fn format_number(value: f64) -> String {
    if value.fract() == 0.0 && value.abs() < 1e15 {
        format!("{}", value as i64)
    } else {
        // Trim noisy floating point tails while keeping useful precision.
        let text = format!("{value:.10}");
        text.trim_end_matches('0').trim_end_matches('.').to_string()
    }
}

fn local_time() -> SearchResult {
    let now = chrono::Local::now();
    let stamp = now.format("%H:%M:%S").to_string();
    SearchResult {
        title: stamp.clone(),
        description: now.format("%A, %d %B %Y").to_string(),
        category: "Time".into(),
        score: 1.0,
        target: None,
        copy_text: Some(stamp),
    }
}

struct BuiltInProvider;

impl SearchProvider for BuiltInProvider {
    fn id(&self) -> &'static str {
        "built-in"
    }

    fn search(&self, _query: &str) -> Result<Vec<SearchResult>, String> {
        // Prefixed providers (calc:, time:) are handled by the engine so they
        // can never be shadowed by an application named like the prefix.
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
        let mut entries: Vec<(String, PathBuf)> = Vec::new();
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
        }
        entries.sort_by_key(|entry| entry.0.to_lowercase());
        entries.dedup_by(|a, b| a.1 == b.1);
        Self { entries }
    }
}

impl SearchProvider for WindowsAppsProvider {
    fn id(&self) -> &'static str {
        "windows-apps"
    }

    fn index_size(&self) -> usize {
        self.entries.len()
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
        let mut entries: Vec<(String, PathBuf)> = Vec::new();
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

    fn index_size(&self) -> usize {
        self.entries.len()
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
#[allow(dead_code)]
fn collect_user_files(_: &std::path::Path, _: usize, _: &mut Vec<(String, PathBuf)>, _: usize) {}

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
    fn prefixes_are_parsed_case_insensitively() {
        assert_eq!(parse_query("CALC: 1 + 1").kind, QueryKind::Calc);
        assert_eq!(parse_query("CALC: 1 + 1").term, "1 + 1");
        assert_eq!(parse_query("  app:code  ").kind, QueryKind::Apps);
        assert_eq!(parse_query("file:report.pdf").kind, QueryKind::Files);
        assert_eq!(parse_query("time:").kind, QueryKind::Time);
    }

    #[test]
    fn urls_paths_and_unknown_prefixes_stay_plain_queries() {
        assert_eq!(parse_query("https://example.com").kind, QueryKind::Auto);
        assert_eq!(parse_query("C:\\Users\\me").kind, QueryKind::Auto);
        assert_eq!(parse_query("wiki: rust").kind, QueryKind::Auto);
        assert_eq!(parse_query("wiki: rust").term, "wiki: rust");
    }

    #[test]
    fn calculator_evaluates_and_returns_copyable_result() {
        let results = SearchEngine::default().search_results("calc: sqrt(81) + 3");
        assert_eq!(results[0].title, "12");
        assert_eq!(results[0].copy_text.as_deref(), Some("12"));
        assert_eq!(results[0].action_label(), "Copy");
    }

    #[test]
    fn plain_arithmetic_is_recognized_without_a_prefix() {
        let results = SearchEngine::default().search_results("6 * 7");
        assert_eq!(results[0].title, "42");
        assert_eq!(results[0].category, "Calculator");
    }

    #[test]
    fn ordinary_words_are_not_treated_as_expressions() {
        assert!(auto_calculator("notepad").is_empty());
        assert!(auto_calculator("2").is_empty());
        assert!(!auto_calculator("2+2").is_empty());
    }

    #[test]
    fn calculator_rejects_invalid_and_non_finite_expressions() {
        let engine = SearchEngine::default();
        assert!(engine.search("calc: 1 / 0").contains("not finite"));
        assert!(engine.search("calc: (").contains("Invalid expression"));
    }

    #[test]
    fn time_prefix_returns_a_copyable_local_time() {
        let results = SearchEngine::default().search_results("time:");
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].category, "Time");
        assert!(results[0].copy_text.is_some());
    }

    #[test]
    fn empty_query_returns_guidance() {
        assert!(
            SearchEngine::default()
                .search("  ")
                .contains("Start typing")
        );
    }

    #[test]
    fn unknown_query_returns_empty_state() {
        assert!(
            SearchEngine::default()
                .search("not-a-real-feature")
                .contains("No results")
        );
    }

    #[test]
    fn app_and_file_prefixes_only_return_their_own_category() {
        let engine = SearchEngine::default();
        for result in engine.search_results("file:anything") {
            assert!(matches!(
                result.category.as_str(),
                "File" | "Folder" | "Status"
            ));
        }
    }

    #[test]
    fn provider_errors_do_not_abort_search() {
        let mut engine = SearchEngine::default();
        engine.register(Box::new(FailingProvider));
        let results = engine.search_results("settings");
        assert!(
            results
                .iter()
                .any(|result| result.title == "failing provider unavailable"),
            "missing status row: {results:?}"
        );
    }

    #[test]
    fn provider_panics_are_contained() {
        let mut engine = SearchEngine::new();
        engine.register(Box::new(PanickingProvider));
        let results = engine.search_results("settings");
        assert!(
            results
                .iter()
                .any(|result| result.title == "panicking provider failed safely"),
            "missing panic status row: {results:?}"
        );
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
    fn ranking_is_deterministic_for_equal_scores() {
        let mut engine = SearchEngine::default();
        engine.register(Box::new(SyntheticProvider));
        let first = engine.search_results("report");
        let second = engine.search_results("report");
        assert_eq!(first, second);
    }

    #[test]
    fn duplicate_targets_are_removed() {
        let mut engine = SearchEngine::new();
        engine.register(Box::new(SyntheticProvider));
        let results = engine.search_results("report");
        let reports: Vec<_> = results
            .iter()
            .filter(|item| item.title.eq_ignore_ascii_case("report"))
            .collect();
        assert_eq!(reports.len(), 1, "duplicate rows kept: {results:?}");
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

    struct SyntheticProvider;

    impl SearchProvider for SyntheticProvider {
        fn id(&self) -> &'static str {
            "windows-apps"
        }

        fn search(&self, _: &str) -> Result<Vec<SearchResult>, String> {
            let target = PathBuf::from("/tmp/report.txt");
            Ok(vec![
                SearchResult {
                    title: "Report".into(),
                    description: "first".into(),
                    category: "Application".into(),
                    score: 0.5,
                    target: Some(target.clone()),
                    copy_text: None,
                },
                SearchResult {
                    title: "Report".into(),
                    description: "duplicate".into(),
                    category: "Application".into(),
                    score: 0.5,
                    target: Some(target),
                    copy_text: None,
                },
            ])
        }
    }
}
