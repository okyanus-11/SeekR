"""Power profile management."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from typing import Any

from core.logging_setup import get_logger

from . import util

log = get_logger(__name__)

_GUID_RE = re.compile(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")


def supported() -> bool:
    if os.name == "nt":
        return util.which("powercfg") is not None
    if sys.platform.startswith("linux"):
        return util.which("powerprofilesctl") is not None
    return False


def _run(args: list[str], timeout: float = 12.0) -> str:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=util.hidden_process_flags(),
            check=False,
        )
        return (completed.stdout or "") + (completed.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        log.info("Power command failed (%s): %s", args, exc)
        return ""


def list_schemes() -> list[dict[str, Any]]:
    """Return available power schemes/profiles with the active flag set."""
    if os.name == "nt":
        output = _run(["powercfg", "/list"])
        active_output = _run(["powercfg", "/getactivescheme"])
        active_match = _GUID_RE.search(active_output)
        active_guid = active_match.group(1).lower() if active_match else ""
        schemes = []
        for line in output.splitlines():
            guid_match = _GUID_RE.search(line)
            if not guid_match:
                continue
            guid = guid_match.group(1)
            name_match = re.search(r"\(([^)]+)\)", line[guid_match.end() :])
            name = name_match.group(1).strip() if name_match else guid
            schemes.append({"id": guid, "name": name, "active": guid.lower() == active_guid})
        return schemes

    if sys.platform.startswith("linux"):
        output = _run(["powerprofilesctl", "list"])
        profiles = []
        for line in output.splitlines():
            match = re.match(r"^\s*(\*)?\s*([A-Za-z0-9_-]+):\s*$", line)
            if not match:
                continue
            profiles.append({"id": match.group(2), "name": match.group(2).title(), "active": bool(match.group(1))})
        return profiles
    return []


def set_scheme(identifier: str) -> tuple[bool, str]:
    """Activate a power scheme/profile."""
    cleaned = (identifier or "").strip()
    if not cleaned:
        return False, "No power profile selected"
    if os.name == "nt":
        if not _GUID_RE.fullmatch(cleaned):
            return False, "Invalid power scheme identifier"
        output = _run(["powercfg", "/setactive", cleaned])
        if "error" in output.lower() or "unable" in output.lower():
            return False, output.strip() or "powercfg could not activate the scheme"
        return True, "Power scheme changed"
    if sys.platform.startswith("linux"):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", cleaned):
            return False, "Invalid power profile identifier"
        output = _run(["powerprofilesctl", "set", cleaned])
        lowered = output.lower()
        if "error" in lowered or "not found" in lowered:
            return False, output.strip() or "powerprofilesctl could not change the profile"
        return True, "Power profile changed"
    return False, "Power profile switching is not supported on this platform"


__all__ = ["supported", "list_schemes", "set_scheme"]
