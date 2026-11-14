"""Dictionary definitions via the free dictionaryapi.dev service."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from core.config_manager import ConfigManager
from core.database import Database
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

log = get_logger(__name__)

ENDPOINT = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
USER_AGENT = "SeekR/1.0 (desktop launcher)"


class DictionaryError(RuntimeError):
    """Raised when a definition cannot be retrieved."""


def lookup(word: str, timeout: float = 8.0) -> dict[str, Any]:
    """Fetch a definition.

    Returns ``{"word": str, "phonetic": str, "meanings": [...]}`` and raises
    :class:`DictionaryError` with a readable message on failure.
    """
    cleaned = (word or "").strip()
    if not cleaned:
        raise DictionaryError("Enter a word to look up")
    url = ENDPOINT.format(word=urllib.parse.quote(cleaned))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 (fixed host)
            payload = json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise DictionaryError(f"No definition found for “{cleaned}”") from exc
        raise DictionaryError(f"Dictionary service returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise DictionaryError("No internet connection or the dictionary service is unreachable") from exc
    except (TimeoutError, OSError) as exc:
        raise DictionaryError("The dictionary request timed out") from exc
    except json.JSONDecodeError as exc:
        raise DictionaryError("The dictionary service returned an unreadable response") from exc

    if not isinstance(payload, list) or not payload:
        raise DictionaryError(f"No definition found for “{cleaned}”")

    entry = payload[0] if isinstance(payload[0], dict) else {}
    meanings: list[dict[str, Any]] = []
    for meaning in entry.get("meanings", []) or []:
        part_of_speech = meaning.get("partOfSpeech", "")
        for definition in meaning.get("definitions", []) or []:
            meanings.append(
                {
                    "partOfSpeech": part_of_speech,
                    "definition": definition.get("definition", ""),
                    "example": definition.get("example", ""),
                    "synonyms": definition.get("synonyms", []) or [],
                }
            )
    return {
        "word": entry.get("word", cleaned),
        "phonetic": entry.get("phonetic", ""),
        "meanings": meanings,
    }


def format_definition(result: dict[str, Any]) -> str:
    """Render a lookup result as readable text."""
    lines = [result.get("word", "").title()]
    if result.get("phonetic"):
        lines.append(result["phonetic"])
    lines.append("")
    for item in result.get("meanings", [])[:8]:
        part = item.get("partOfSpeech", "")
        lines.append(f"({part}) {item.get('definition', '')}".strip())
        if item.get("example"):
            lines.append(f"   “{item['example']}”")
        if item.get("synonyms"):
            lines.append(f"   synonyms: {', '.join(item['synonyms'][:6])}")
        lines.append("")
    return "\n".join(lines).strip()


class DefineProvider(SearchProvider):
    """The ``define:`` keyword."""

    id = "dictionary"
    title = "Dictionary"
    keyword = "define"
    weight = 1.0
    auto = False

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip()
        if not text:
            return []
        word = text.split()[0]
        url = f"https://www.merriam-webster.com/dictionary/{urllib.parse.quote(word)}"
        return [
            self.make_result(
                title=f"Look up “{word}”",
                subtitle="Fetch the definition from the dictionary service",
                category="Web",
                score=0.95,
                primary=lambda: self.hooks.lookup_definition(word),
                actions=[
                    ResultAction(
                        "Search Wikipedia instead",
                        lambda: self.hooks.open_url(
                            f"https://en.wikipedia.org/w/index.php?search={urllib.parse.quote(word)}"
                        ),
                    ),
                    ResultAction("Open Merriam-Webster", lambda: self.hooks.open_url(url)),
                    ResultAction("Copy word", lambda: self.hooks.copy_text(word)),
                ],
                copy_text=word,
                icon_glyph="A",
                meta={"word": word, "url": url},
            )
        ]

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Dictionary",
            subtitle="Try: define: algorithm",
            category="Web",
            score=1.0,
            primary=lambda: self.hooks.fill_query("define: algorithm"),
            icon_glyph="A",
        )


__all__ = ["lookup", "format_definition", "DictionaryError", "DefineProvider"]
