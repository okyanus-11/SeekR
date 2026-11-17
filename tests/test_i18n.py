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
