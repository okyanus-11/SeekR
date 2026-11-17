from __future__ import annotations

from ui import i18n


class FakeConfig:
    def __init__(self, language: str):
        self.language = language

    def get(self, key: str, default=None):
        return self.language if key == "general.language" else default


def test_all_nine_languages_have_launcher_and_tools_navigation_strings():
    assert len(i18n.LANGUAGES) == 9
    for code in i18n.LANGUAGES:
        config = FakeConfig(code)
        assert i18n.language_of(config) == code
        assert i18n.tr(config, "launcher.placeholder")
        assert i18n.tr(config, "tools.page.calculator") != "tools.page.calculator"


def test_common_locale_aliases_are_normalized():
    assert i18n.language_of(FakeConfig("pt_br")) == "pt-BR"
    assert i18n.language_of(FakeConfig("zh")) == "zh-CN"
    assert i18n.language_of(FakeConfig("unsupported")) == "en"


def test_formatted_translations_preserve_interpolated_values():
    assert i18n.tr(FakeConfig("es"), "launcher.action.selected", name="Open") == "Acción: Open"


def test_shared_widget_labels_use_the_active_language():
    i18n.set_language(FakeConfig("de"))
    assert i18n.translate_text("Appearance") == "Darstellung"
    assert i18n.translate_text("Save") == "Speichern"
    assert i18n.translate_text("An application-specific label") == "An application-specific label"
    i18n.set_language(FakeConfig("en"))
    assert i18n.translate_text("Appearance") == "Appearance"
