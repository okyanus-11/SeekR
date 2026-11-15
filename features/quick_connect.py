"""SSH connection profiles (key-based only, never passwords)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import fuzzy_score
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

from . import util

log = get_logger(__name__)

HOST_RE = re.compile(r"^[A-Za-z0-9._\-\[\]:]+$")
USER_RE = re.compile(r"^[A-Za-z0-9._\-]*$")


class ConnectionError_(RuntimeError):
    """Raised when an SSH profile cannot be used."""


def validate_profile(data: dict[str, Any]) -> tuple[bool, str]:
    name = str(data.get("name", "")).strip()
    host = str(data.get("host", "")).strip()
    user = str(data.get("user", "")).strip()
    port = data.get("port", 22)
    if not name:
        return False, "A profile name is required"
    if not host:
        return False, "A host is required"
    if not HOST_RE.match(host):
        return False, "The host contains unsupported characters"
    if user and not USER_RE.match(user):
        return False, "The user name contains unsupported characters"
    try:
        port_value = int(port)
    except (TypeError, ValueError):
        return False, "The port must be a number"
    if not (1 <= port_value <= 65535):
        return False, "The port must be between 1 and 65535"
    key_path = str(data.get("key_path", "")).strip()
    if key_path and not Path(key_path).expanduser().exists():
        return False, f"Private key not found: {key_path}"
    return True, ""


def build_ssh_argv(profile: dict[str, Any]) -> list[str]:
    """Build the ssh argument list for a saved profile."""
    host = str(profile.get("host", "")).strip()
    user = str(profile.get("user", "")).strip()
    if not host or not HOST_RE.match(host):
        raise ConnectionError_("This profile has an invalid host")
    if user and not USER_RE.match(user):
        raise ConnectionError_("This profile has an invalid user name")
    target = f"{user}@{host}" if user else host
    args = ["ssh"]
    try:
        port = int(profile.get("port", 22) or 22)
    except (TypeError, ValueError):
        port = 22
    if port != 22:
        args.extend(["-p", str(port)])
    key_path = str(profile.get("key_path", "")).strip()
    if key_path:
        args.extend(["-i", str(Path(key_path).expanduser())])
    extras = util.split_args(str(profile.get("extra_args", "") or ""))
    args.extend(extras)
    args.append(target)
    return args


def _terminal_command(ssh_args: list[str]) -> list[str] | None:
    """Wrap ssh arguments in the best available terminal emulator."""
    if os.name == "nt":
        terminal = util.which("wt.exe") or util.which("wt")
        if terminal:
            return [terminal, "new-tab", "--", *ssh_args]
        return None
    terminals = [
        ("gnome-terminal", lambda args: ["gnome-terminal", "--", *args]),
        ("konsole", lambda args: ["konsole", "-e", *args]),
        ("alacritty", lambda args: ["alacritty", "-e", *args]),
        ("kitty", lambda args: ["kitty", *args]),
        ("xfce4-terminal", lambda args: ["xfce4-terminal", "-e", " ".join(args)]),
        ("x-terminal-emulator", lambda args: ["x-terminal-emulator", "-e", *args]),
        ("xterm", lambda args: ["xterm", "-e", *args]),
    ]
    for executable, builder in terminals:
        if util.which(executable):
            return builder(ssh_args)
    return None


def _launch_ssh_in_new_console(ssh_args: list[str]) -> tuple[bool, str]:
    """Launch SSH directly with a fresh Windows console and no command shell."""
    try:
        subprocess.Popen(
            ssh_args,
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            close_fds=True,
        )
        return True, f"Started {ssh_args[0]}"
    except OSError as exc:
        log.error("Could not start %s: %s", ssh_args, exc)
        return False, f"Could not start {ssh_args[0]}: {exc}"


def launch_profile(profile: dict[str, Any]) -> tuple[bool, str]:
    try:
        ssh_args = build_ssh_argv(profile)
    except ConnectionError_ as exc:
        return False, str(exc)
    ssh_client = util.which("ssh")
    if ssh_client is None:
        return False, "The OpenSSH client (ssh) is not installed or not on PATH"
    if os.name == "nt":
        command = _terminal_command(ssh_args)
        if command is not None:
            return util.run_detached(command)
        return _launch_ssh_in_new_console(ssh_args)
    command = _terminal_command(ssh_args)
    if command is None:
        return False, "No supported terminal emulator was found"
    return util.run_detached(command)


class QuickConnectService:
    """CRUD and execution of SSH profiles stored in SQLite."""

    def __init__(self, config: ConfigManager, db: Database):
        self.config = config
        self.db = db

    def profiles(self) -> list[dict]:
        return self.db.list_ssh_profiles()

    def save(self, data: dict) -> tuple[bool, str]:
        ok, message = validate_profile(data)
        if not ok:
            return False, message
        result = self.db.upsert_ssh_profile(data)
        if result < 0:
            return False, "Could not save the profile"
        return True, ""

    def delete(self, profile_id: int) -> None:
        self.db.delete_ssh_profile(profile_id)

    def connect(self, profile: dict) -> tuple[bool, str]:
        return launch_profile(profile)

    def search(self, query: str, limit: int = 8) -> list[dict]:
        profiles = self.profiles()
        text = (query or "").strip()
        if not text:
            return profiles[:limit]
        scored = []
        for profile in profiles:
            haystack = f"{profile['name']} {profile.get('host', '')} {profile.get('user', '')}"
            score = fuzzy_score(text, haystack, typo_tolerance=True)
            if score > 0:
                scored.append((score, profile))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [profile for _, profile in scored[:limit]]


class SSHProvider(SearchProvider):
    """The ``ssh`` keyword."""

    id = "ssh"
    title = "SSH connections"
    keyword = "ssh"
    weight = 0.95
    auto = False

    def __init__(self, config, db, hooks, service: QuickConnectService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or QuickConnectService(config, db)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        profiles = self.service.search(query, limit)
        if not profiles:
            return [
                self.make_result(
                    title="No SSH profiles saved",
                    subtitle="Add a connection in Tools → Quick Connect (key-based authentication only)",
                    category="Connection",
                    score=0.8,
                    primary=lambda: self.hooks.open_tools("connections"),
                    icon_glyph="⇌",
                )
            ]
        return [self._result(profile, 0.9 - index * 0.02) for index, profile in enumerate(profiles)]

    def _result(self, profile: dict, score: float) -> SearchResult:
        target = f"{profile.get('user') + '@' if profile.get('user') else ''}{profile.get('host')}:{profile.get('port', 22)}"
        try:
            command = " ".join(build_ssh_argv(profile))
        except ConnectionError_:
            command = ""
        return self.make_result(
            title=profile.get("name", "SSH connection"),
            subtitle=f"{target}  ·  key-based authentication",
            category="Connection",
            score=score,
            primary=lambda: self._connect(profile),
            actions=[
                ResultAction("Copy ssh command", lambda: self.hooks.copy_text(command)),
                ResultAction("Manage profiles", lambda: self.hooks.open_tools("connections")),
            ],
            copy_text=command,
            icon_glyph="⇌",
            meta={"profile": profile},
        )

    def _connect(self, profile: dict) -> None:
        ok, message = self.service.connect(profile)
        self.hooks.notify(message, "info" if ok else "error")
        if ok:
            self.hooks.hide_launcher()
        else:
            self.hooks.show_error("SSH connection failed", message)

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="SSH connections",
            subtitle="Type part of a saved profile name, or manage profiles in Tools",
            category="Connection",
            score=1.0,
            primary=lambda: self.hooks.open_tools("connections"),
            icon_glyph="⇌",
        )


__all__ = [
    "QuickConnectService",
    "SSHProvider",
    "build_ssh_argv",
    "validate_profile",
    "launch_profile",
]
