from ui.themes import DESIGN_TOKENS, THEMES, build_stylesheet, palette_for, tokens_for


def test_every_theme_exposes_complete_semantic_roles():
    required = {"window", "surface", "border", "text", "muted", "accent",
                "danger", "success", "warning", "focus", "disabled", "error",
                "selection", "info"}
    for theme in THEMES:
        assert required <= palette_for(theme).keys()


def test_shared_design_tokens_are_copy_safe():
    spacing = tokens_for("spacing")
    assert spacing["md"] == 12
    spacing["md"] = 999
    assert tokens_for("spacing")["md"] == DESIGN_TOKENS["spacing"]["md"]


def test_theme_stylesheet_has_visible_keyboard_focus(config):
    stylesheet = build_stylesheet(config)
    assert "QPushButton:focus" in stylesheet
    assert "QTableWidget:focus" in stylesheet
    assert "border: 2px solid" in stylesheet
