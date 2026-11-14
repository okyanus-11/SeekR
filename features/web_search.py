"""Web search integrations."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote, quote_plus

from core.config_manager import ConfigManager
from core.constants import WEB_ENGINES
from core.database import Database
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

from . import util

log = get_logger(__name__)

LANGUAGES = {
    "turkish": "tr", "turkce": "tr", "türkçe": "tr", "english": "en", "german": "de",
    "deutsch": "de", "french": "fr", "français": "fr", "spanish": "es", "español": "es",
    "italian": "it", "portuguese": "pt", "russian": "ru", "arabic": "ar", "japanese": "ja",
    "korean": "ko", "chinese": "zh-CN", "dutch": "nl", "polish": "pl", "swedish": "sv",
    "greek": "el", "hindi": "hi", "ukrainian": "uk", "persian": "fa", "farsi": "fa",
    "hebrew": "he", "azerbaijani": "az", "indonesian": "id", "thai": "th",
    "vietnamese": "vi", "czech": "cs", "romanian": "ro", "hungarian": "hu",
    "finnish": "fi", "danish": "da", "norwegian": "no", "bulgarian": "bg",
    "serbian": "sr", "croatian": "hr", "slovak": "sk", "kazakh": "kk", "auto": "auto",
}


class WebService:
    """Builds search URLs and opens them in the configured browser."""

    def __init__(self, config: ConfigManager, hooks, db: Database | None = None):
        self.config = config
        self.hooks = hooks
        self.db = db

    # --------------------------------------------------------------- engines
    def engines(self) -> dict[str, dict[str, str]]:
        configured = self.config.get("web.engines", {}) or {}
        engines = {key: dict(value) for key, value in WEB_ENGINES.items()}
        if isinstance(configured, dict):
            for key, value in configured.items():
                if isinstance(value, dict) and value.get("url"):
                    engines[str(key)] = {
                        "label": str(value.get("label") or key.title()),
                        "url": str(value["url"]),
                    }
        return engines

    def engine_label(self, engine: str) -> str:
        engines = self.engines()
        return engines.get(engine, {}).get("label", engine.title())

    def default_engine(self) -> str:
        engine = str(self.config.get("web.engine", "duckduckgo") or "duckduckgo")
        return engine if engine in self.engines() else "duckduckgo"

    def build_url(self, query: str, engine: str | None = None) -> str:
        engines = self.engines()
        engine = engine or self.default_engine()
        if engine not in engines:
            engine = self.default_engine()
        template = engines[engine]["url"]
        encoded = quote_plus(query.strip())
        if "{query}" in template:
            return template.replace("{query}", encoded)
        return template + encoded

    # ----------------------------------------------------------------- opening
    def open(self, query: str, engine: str | None = None) -> tuple[bool, str]:
        url = self.build_url(query, engine)
        browser = str(self.config.get("web.browser", "system") or "system")
        if browser.lower() not in {"system", "default", ""}:
            path = Path(browser).expanduser()
            if path.exists():
                ok, message = util.run_detached([str(path), url])
                if ok:
                    self._record(query, engine)
                    return True, f"Opened {url}"
                log.warning("Configured browser could not be started: %s", message)
        ok = self.hooks.open_url(url)
        if ok:
            self._record(query, engine)
            return True, f"Opened {self.engine_label(engine or self.default_engine())}"
        return False, f"Could not open the browser. URL: {url}"

    def _record(self, query: str, engine: str | None) -> None:
        if self.db is not None and query.strip():
            self.db.add_history("web", query.strip())

    def translate_url(self, text: str, target: str = "en", source: str = "auto") -> str:
        return (
            "https://translate.google.com/?sl="
            f"{quote(source)}&tl={quote(target)}&text={quote(text)}&op=translate"
        )

    def definition_url(self, word: str) -> str:
        return f"https://www.merriam-webster.com/dictionary/{quote(word.strip())}"


class _SingleEngineProvider(SearchProvider):
    """Shared implementation for search-engine keyword providers."""

    engine = "duckduckgo"
    label = "the web"
    glyph = "🌐"

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip()
        if not text:
            return []
        service: WebService = getattr(self, "web", None)
        if service is None:
            return []
        engine = self.engine
        url = service.build_url(text, engine)
        engines = service.engines()
        actions = []
        for key, meta in engines.items():
            if key == engine:
                continue
            actions.append(
                ResultAction(
                    f"Search {meta['label']}",
                    lambda k=key: self._open(text, k),
                )
            )
        actions.append(ResultAction("Copy search URL", lambda: self.hooks.copy_text(url)))
        return [
            self.make_result(
                title=f"Search {self.label} for “{text}”",
                subtitle=url,
                category="Web",
                score=0.9,
                primary=lambda: self._open(text, engine),
                actions=actions,
                copy_text=url,
                icon_glyph=self.glyph,
                meta={"url": url, "engine": engine},
            )
        ]

    def _open(self, text: str, engine: str) -> None:
        service: WebService = getattr(self, "web", None)
        if service is None:
            return
        ok, message = service.open(text, engine)
        self.hooks.notify(message, "info" if ok else "error")
        if ok:
            self.hooks.hide_launcher()


class WebProvider(_SingleEngineProvider):
    """Automatic web search suggestion plus the ``web:`` keyword."""

    id = "web"
    title = "Web search"
    keyword = "web"
    weight = 0.45
    auto = True
    glyph = "🌐"

    def __init__(self, config, db, hooks, service: WebService | None = None):
        super().__init__(config, db, hooks)
        self.web = service or WebService(config, hooks, db)

    @property
    def engine(self) -> str:  # type: ignore[override]
        return self.web.default_engine()

    @property
    def label(self) -> str:  # type: ignore[override]
        return self.web.engine_label(self.engine)


class WikipediaProvider(_SingleEngineProvider):
    id = "wikipedia"
    title = "Wikipedia"
    keyword = "wiki"
    weight = 0.95
    auto = False
    engine = "wikipedia"
    label = "Wikipedia"
    glyph = "W"

    def __init__(self, config, db, hooks, service: WebService | None = None):
        super().__init__(config, db, hooks)
        self.web = service or WebService(config, hooks, db)


class YouTubeProvider(_SingleEngineProvider):
    id = "youtube"
    title = "YouTube"
    keyword = "yt"
    weight = 0.95
    auto = False
    engine = "youtube"
    label = "YouTube"
    glyph = "▶"

    def __init__(self, config, db, hooks, service: WebService | None = None):
        super().__init__(config, db, hooks)
        self.web = service or WebService(config, hooks, db)


class GitHubProvider(_SingleEngineProvider):
    id = "github"
    title = "GitHub"
    keyword = "gh"
    weight = 0.95
    auto = False
    engine = "github"
    label = "GitHub"
    glyph = "⌥"

    def __init__(self, config, db, hooks, service: WebService | None = None):
        super().__init__(config, db, hooks)
        self.web = service or WebService(config, hooks, db)


class TranslateProvider(SearchProvider):
    """``translate: Hello to Turkish``."""

    id = "translate"
    title = "Translate"
    keyword = "translate"
    weight = 1.0
    auto = False

    def __init__(self, config, db, hooks, service: WebService | None = None):
        super().__init__(config, db, hooks)
        self.web = service or WebService(config, hooks, db)

    def _parse(self, text: str) -> tuple[str, str] | None:
        import re

        match = re.match(r"^(.*?)\s+(?:to|into|->|→)\s+([A-Za-zÇĞİÖŞÜçğıöşü ]+)$", text.strip(), re.IGNORECASE)
        if not match:
            return None
        phrase = match.group(1).strip()
        language_name = match.group(2).strip().lower()
        code = LANGUAGES.get(language_name)
        if code is None:
            return None
        return phrase, code

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip()
        if not text:
            return []
        parsed = self._parse(text)
        if parsed is None:
            return [
                self.make_result(
                    title="Translate text",
                    subtitle="Use: translate: Hello to Turkish",
                    category="Web",
                    score=0.9,
                    icon_glyph="A",
                )
            ]
        phrase, code = parsed
        url = self.web.translate_url(phrase, target=code)
        label = next(
            (name.title() for name, value in LANGUAGES.items() if value == code),
            code,
        )
        return [
            self.make_result(
                title=f"Translate into {label}",
                subtitle=f"“{phrase}” → {label}  ·  {url}",
                category="Web",
                score=0.95,
                primary=lambda: self._open(url),
                actions=[ResultAction("Copy URL", lambda: self.hooks.copy_text(url))],
                copy_text=phrase,
                icon_glyph="A",
                meta={"url": url},
            )
        ]

    def _open(self, url: str) -> None:
        if self.hooks.open_url(url):
            self.hooks.hide_launcher()

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Translate",
            subtitle="Try: translate: Hello to Turkish",
            category="Web",
            score=1.0,
            primary=lambda: self.hooks.fill_query("translate: Hello to Turkish"),
            icon_glyph="A",
        )


__all__ = [
    "WebService",
    "WebProvider",
    "WikipediaProvider",
    "YouTubeProvider",
    "GitHubProvider",
    "TranslateProvider",
    "LANGUAGES",
]
