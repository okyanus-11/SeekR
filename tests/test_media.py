from __future__ import annotations

import pytest

from features import media


def test_media_api_reports_unsupported_platform_cleanly(monkeypatch):
    monkeypatch.setattr(media.sys, "platform", "linux")
    with pytest.raises(media.MediaUnavailableError, match="Windows only"):
        media.get_current_media()


def test_media_widget_renders_session_and_supported_controls(qapp):
    from PySide6.QtCore import QThreadPool
    from ui.launcher_widgets import MediaWidget

    widget = MediaWidget(QThreadPool())
    widget.set_media({
        "title": "Test track",
        "artist": "Test artist",
        "album": "Test album",
        "status": "playing",
        "can_play": True,
        "can_pause": True,
        "can_toggle": True,
        "can_next": True,
        "can_previous": False,
        "source": "TestPlayer",
    })
    assert widget.title.text() == "Test track"
    assert "Test artist" in widget.artist.text()
    assert widget.status.text().startswith("Playing")
    assert widget.play_pause_button.text() == "Pause"
    assert widget.play_pause_button.isEnabled()
    assert widget.next_button.isEnabled()
    assert not widget.previous_button.isEnabled()
    widget.timer.stop()
    widget.deleteLater()
