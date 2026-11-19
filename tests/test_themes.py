from PySide6.QtCore import QAbstractAnimation
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



def test_switch_respects_reduced_motion_preference(qapp, config):
    from ui.components import Switch
    from ui.themes import apply_theme

    config.set("appearance.animations", False)
    apply_theme(qapp, config)
    switch = Switch()
    switch.setChecked(True)
    assert switch._position == 1.0
    assert switch._animation.state() == QAbstractAnimation.State.Stopped

    config.set("appearance.animations", True)
    apply_theme(qapp, config)
    switch.setChecked(False)
    assert switch._animation.endValue() == 0.0
    switch._animation.stop()
