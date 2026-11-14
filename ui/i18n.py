"""Minimal localization for the launcher shell.

SeekR 1.0.0 ships fully in English; the Turkish table covers the launcher
surface (placeholder, hints, empty state) so the language setting has a real
effect. Everything else falls back to English.
"""

from __future__ import annotations

LANGUAGES = {"en": "English", "tr": "Türkçe"}

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "launcher.placeholder": "Search applications, files, commands or type an expression…",
        "launcher.hint.navigate": "↑↓ Navigate",
        "launcher.hint.open": "Enter Open",
        "launcher.hint.actions": "Tab Actions",
        "launcher.hint.copy": "Ctrl+C Copy",
        "launcher.hint.close": "Esc Close",
        "launcher.empty.title": "Start typing to search",
        "launcher.empty.body": "Applications, files and quick actions appear as you type.",
        "launcher.noresults.title": "No results found",
        "launcher.noresults.body": "Try a different spelling, or use a keyword such as calc: or file:.",
        "launcher.settings": "Settings",
        "launcher.action.next": "Tab for next action",
        "launcher.action.selected": "Action: {name}",
        "launcher.results": "{count} results",
        "launcher.single_result": "1 result",
    },
    "tr": {
        "launcher.placeholder": "Uygulama, dosya veya komut arayın ya da bir ifade yazın…",
        "launcher.hint.navigate": "↑↓ Gezin",
        "launcher.hint.open": "Enter Aç",
        "launcher.hint.actions": "Tab Eylemler",
        "launcher.hint.copy": "Ctrl+C Kopyala",
        "launcher.hint.close": "Esc Kapat",
        "launcher.empty.title": "Aramak için yazmaya başlayın",
        "launcher.empty.body": "Yazdıkça uygulamalar, dosyalar ve hızlı eylemler görünür.",
        "launcher.noresults.title": "Sonuç bulunamadı",
        "launcher.noresults.body": "Farklı bir yazım deneyin veya calc: ya da file: gibi bir anahtar kelime kullanın.",
        "launcher.settings": "Ayarlar",
        "launcher.action.next": "Sonraki eylem için Tab",
        "launcher.action.selected": "Eylem: {name}",
        "launcher.results": "{count} sonuç",
        "launcher.single_result": "1 sonuç",
    },
}


def language_of(config) -> str:
    value = str(config.get("general.language", "en") or "en").lower()
    return value if value in _STRINGS else "en"


def tr(config, key: str, **kwargs) -> str:
    """Translate *key* for the configured language."""
    language = language_of(config)
    template = _STRINGS.get(language, {}).get(key) or _STRINGS["en"].get(key, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template


__all__ = ["LANGUAGES", "language_of", "tr"]
