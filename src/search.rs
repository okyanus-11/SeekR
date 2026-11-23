use std::panic::{catch_unwind, AssertUnwindSafe};

#[derive(Debug, Clone, PartialEq)]
pub struct SearchResult {
    pub title: String,
    pub description: String,
    pub category: String,
    pub score: f32,
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
        Self { providers: vec![Box::new(BuiltInProvider)] }
    }

    pub fn register(&mut self, provider: Box<dyn SearchProvider>) {
        self.providers.retain(|existing| existing.id() != provider.id());
        self.providers.push(provider);
    }

    pub fn search(&self, query: &str) -> String {
        let query = query.trim();
        if query.is_empty() {
            return "Start typing to search.\n\nTry: calculator, settings, reindex, system".into();
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
                }),
                Err(_) => results.push(SearchResult {
                    title: format!("{} provider failed safely", provider.id()),
                    description: "A provider panicked; other providers remain available.".into(),
                    category: "Status".into(),
                    score: 0.0,
                }),
            }
        }

        results.sort_by(|a, b| {
            b.score.total_cmp(&a.score)
                .then_with(|| a.title.to_lowercase().cmp(&b.title.to_lowercase()))
        });
        results.truncate(12);

        if results.is_empty() {
            return format!("No results for “{query}”.");
        }
        results.into_iter()
            .map(|item| format!("{}\n{}  ·  {}", item.title, item.description, item.category))
            .collect::<Vec<_>>()
            .join("\n\n")
    }
}

impl Default for SearchEngine {
    fn default() -> Self { Self::new() }
}

struct BuiltInProvider;

impl SearchProvider for BuiltInProvider {
    fn id(&self) -> &'static str { "built-in" }

    fn search(&self, query: &str) -> Result<Vec<SearchResult>, String> {
        let entries = [
            ("Calculator", "Evaluate a mathematical expression", "Tool"),
            ("Settings", "Configure SeekR and its widgets", "Application"),
            ("Reindex apps and files", "Refresh the local search index", "Action"),
            ("System information", "View CPU, memory and device details", "Tool"),
            ("Clipboard history", "Browse locally stored clipboard entries", "Tool"),
            ("Focus timer", "Start or manage a focus session", "Widget"),
        ];
        Ok(entries.into_iter().filter_map(|(title, description, category)| {
            let score = match_score(query, title, description);
            if score > 0.0 {
                Some(SearchResult {
                    title: title.into(),
                    description: description.into(),
                    category: category.into(),
                    score,
                })
            } else {
                None
            }
        }).collect())
    }
}

fn match_score(query: &str, title: &str, description: &str) -> f32 {
    let query = query.to_lowercase();
    let title = title.to_lowercase();
    let description = description.to_lowercase();
    if query.is_empty() { return 0.0; }
    if title == query { return 1.0; }
    if title.starts_with(&query) { return 0.92; }
    if title.contains(&query) { return 0.82; }
    if description.contains(&query) { return 0.62; }

    let tokens: Vec<_> = query.split_whitespace().collect();
    if !tokens.is_empty()
        && tokens.iter().all(|token| title.split_whitespace().any(|part| part.starts_with(token)))
    {
        return 0.72;
    }
    if is_subsequence(&query, &title) { return 0.45; }
    0.0
}

fn is_subsequence(needle: &str, haystack: &str) -> bool {
    let mut chars = haystack.chars();
    needle.chars().all(|wanted| chars.any(|actual| actual == wanted))
}

#[cfg(test)]
mod tests {
    use super::*;

    struct FailingProvider;
    impl SearchProvider for FailingProvider {
        fn id(&self) -> &'static str { "failing" }
        fn search(&self, _: &str) -> Result<Vec<SearchResult>, String> { Err("test failure".into()) }
    }

    struct PanickingProvider;
    impl SearchProvider for PanickingProvider {
        fn id(&self) -> &'static str { "panicking" }
        fn search(&self, _: &str) -> Result<Vec<SearchResult>, String> { panic!("simulated provider panic"); }
    }

    #[test]
    fn exact_matches_rank_above_prefix_and_substring() {
        assert!(SearchEngine::default().search("settings").starts_with("Settings"));
    }

    #[test]
    fn matching_is_case_insensitive_and_typo_tolerant() {
        let engine = SearchEngine::default();
        assert!(engine.search("CALC").contains("Calculator"));
        assert!(engine.search("clculator").contains("Calculator"));
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
        assert!(output.contains("Settings"));
        assert!(output.contains("provider unavailable"));
    }

    #[test]
    fn provider_panics_are_contained() {
        let mut engine = SearchEngine::default();
        engine.register(Box::new(PanickingProvider));
        let output = engine.search("settings");
        assert!(output.contains("Settings"));
        assert!(output.contains("failed safely"));
    }

    #[test]
    fn registering_same_provider_replaces_it() {
        let mut engine = SearchEngine::default();
        engine.register(Box::new(FailingProvider));
        engine.register(Box::new(FailingProvider));
        assert_eq!(engine.providers.iter().filter(|p| p.id() == "failing").count(), 1);
    }
}
