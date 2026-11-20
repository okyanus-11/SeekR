"""Optional Windows system-media-session integration.

The WinRT dependency is installed only on Windows with Python 3.11+.
All calls run from a worker thread and fail closed when the API is unavailable.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any


class MediaUnavailableError(RuntimeError):
    """Raised when the Windows media-session API is unavailable."""


def _media_api():
    if sys.platform != "win32":
        raise MediaUnavailableError("System media controls are available on Windows only.")
    if sys.version_info < (3, 11):
        raise MediaUnavailableError("System media controls require Python 3.11 or newer.")
    try:
        from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    except ImportError as exc:
        raise MediaUnavailableError("Windows media-control support is not installed.") from exc
    return GlobalSystemMediaTransportControlsSessionManager


async def _get_snapshot() -> dict[str, Any] | None:
    manager_type = _media_api()
    manager = await manager_type.request_async()
    session = manager.get_current_session()
    if session is None:
        return None
    properties = await session.try_get_media_properties_async()
    playback = session.get_playback_info()
    controls = playback.controls
    status = getattr(playback.playback_status, "name", str(playback.playback_status)).lower()
    return {
        "title": str(properties.title or "").strip(),
        "artist": str(properties.artist or properties.album_artist or "").strip(),
        "album": str(properties.album_title or "").strip(),
        "status": status,
        "can_play": bool(controls and controls.is_play_enabled),
        "can_pause": bool(controls and controls.is_pause_enabled),
        "can_toggle": bool(controls and controls.is_play_pause_toggle_enabled),
        "can_next": bool(controls and controls.is_next_enabled),
        "can_previous": bool(controls and controls.is_previous_enabled),
        "source": str(session.source_app_user_model_id or "").split("!")[-1][:80],
    }


async def _send_command(action: str) -> bool:
    manager_type = _media_api()
    manager = await manager_type.request_async()
    session = manager.get_current_session()
    if session is None:
        return False
    methods = {
        "play": session.try_play_async,
        "pause": session.try_pause_async,
        "toggle": session.try_toggle_play_pause_async,
        "next": session.try_skip_next_async,
        "previous": session.try_skip_previous_async,
    }
    method = methods.get(action)
    if method is None:
        raise ValueError("Unsupported media command.")
    return bool(await method())


def get_current_media() -> dict[str, Any] | None:
    """Return current-session metadata without blocking the GUI thread."""
    return asyncio.run(_get_snapshot())


def control_current_media(action: str) -> bool:
    """Send a supported playback command to the current Windows media session."""
    return asyncio.run(_send_command(action))


__all__ = ["MediaUnavailableError", "get_current_media", "control_current_media"]
