"""Built-in and user-defined command execution."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import fuzzy_score
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

from . import util

log = get_logger(__name__)


@dataclass
class CommandOutcome:
    success: bool
    message: str = ""
    output: str = ""


@dataclass
class CommandEntry:
    key: str
    title: str
    description: str
    destructive: bool = False
    builtin: bool = True
    aliases: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @property
    def confirmation(self) -> bool:
        if self.builtin:
            return self.destructive
        return bool(self.raw.get("confirm", 1))



def split_command_chain(expression: str) -> list[str]:
    """Split on the word 'then' only outside quoted command arguments."""
    parts: list[str] = []
    start = 0
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(expression):
        char = expression[index]
        if escaped:
            escaped = False
            index += 1
            continue
        if (quote == '"' and char == "\\" and index + 1 < len(expression)
                and expression[index + 1] in {'"', "\\"}):
            escaped = True
            index += 1
            continue
        if quote:
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if char.isspace():
            match = re.match(r"\s+then\s+", expression[index:], flags=re.IGNORECASE)
            if match:
                parts.append(expression[start:index].strip())
                index += match.end()
                start = index
                continue
        index += 1
    parts.append(expression[start:].strip())
    return parts


class CommandService:
    """Executes system commands without ever invoking a shell."""

    def __init__(self, config: ConfigManager, db: Database, hooks):
        self.config = config
        self.db = db
        self.hooks = hooks
        self._handlers: dict[str, Callable[[list[str]], CommandOutcome]] = {
            "shutdown": self._shutdown,
            "restart": self._restart,
            "sleep": self._sleep,
            "lock": self._lock,
            "settings": self._settings,
            "taskmgr": self._taskmgr,
            "terminal": self._terminal,
            "explorer": self._explorer,
            "ipconfig": self._ipconfig,
            "empty_recycle": self._empty_recycle,
        }
        self._builtins: list[CommandEntry] = [
            CommandEntry("shutdown", "Shut down", "Turn off the computer", destructive=True),
            CommandEntry("restart", "Restart", "Restart the computer", destructive=True),
            CommandEntry("sleep", "Sleep", "Put the computer to sleep", destructive=True),
            CommandEntry("lock", "Lock", "Lock the current session"),
            CommandEntry("settings", "Windows Settings", "Open the Windows Settings app"),
            CommandEntry("taskmgr", "Task Manager", "Open the Task Manager"),
            CommandEntry("terminal", "Terminal", "Open a terminal window"),
            CommandEntry("explorer", "File Explorer", "Open File Explorer"),
            CommandEntry("ipconfig", "IP configuration", "Show network interface details"),
            CommandEntry(
                "empty_recycle",
                "Empty Recycle Bin",
                "Permanently delete everything in the Recycle Bin",
                destructive=True,
                aliases=["empty trash", "recycle"],
            ),
        ]

    # ------------------------------------------------------------------ lists
    def builtins(self) -> list[CommandEntry]:
        return list(self._builtins)

    def custom_commands(self) -> list[CommandEntry]:
        entries = []
        for row in self.db.list_custom_commands():
            aliases = [alias.strip() for alias in str(row.get("aliases", "")).split(",") if alias.strip()]
            entries.append(
                CommandEntry(
                    key=f"custom:{row['id']}",
                    title=row["name"],
                    description=row.get("description", "") or f"Run {row['command']}",
                    builtin=False,
                    aliases=aliases,
                    raw=dict(row),
                )
            )
        return entries

    def entries(self) -> list[CommandEntry]:
        return self.builtins() + self.custom_commands()

    def search(self, query: str, limit: int = 8) -> list[CommandEntry]:
        text = (query or "").strip()
        entries = self.entries()
        if not text:
            return entries[:limit]
        scored: list[tuple[float, CommandEntry]] = []
        for entry in entries:
            score = fuzzy_score(text, entry.title, typo_tolerance=True)
            score = max(score, fuzzy_score(text, entry.key.replace("custom:", ""), typo_tolerance=True))
            score = max(score, fuzzy_score(text, entry.description, typo_tolerance=True) * 0.8)
            for alias in entry.aliases:
                score = max(score, fuzzy_score(text, alias, typo_tolerance=True))
            if score >= 0.4:
                scored.append((score, entry))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [entry for _, entry in scored[:limit]]

    def needs_confirmation(self, entry: CommandEntry) -> bool:
        # Both the global safety switch (Settings → General) and the command
        # specific confirmation flag must allow the action.
        if not self.config.get("general.confirm_destructive_actions", True):
            return False
        if not self.config.get("commands.confirm_destructive", True):
            return False
        return entry.confirmation

    # --------------------------------------------------------------- execution
    def run(self, entry: CommandEntry, args_text: str = "") -> CommandOutcome:
        return self.run_arguments(entry, util.split_args(args_text))

    def run_arguments(self, entry: CommandEntry, arguments: list[str]) -> CommandOutcome:
        """Run an existing command with already-tokenized arguments, without a shell."""
        if len(arguments) > 64 or not all(
            isinstance(arg, str) and len(arg) <= 2048 for arg in arguments
        ):
            return CommandOutcome(False, "Command arguments must be strings of at most 2048 characters (64 maximum)")
        if entry.builtin:
            handler = self._handlers.get(entry.key)
            if handler is None:
                return CommandOutcome(False, f"Unknown command: {entry.title}")
            try:
                outcome = handler(list(arguments))
            except Exception as exc:
                log.exception("Built-in command %s failed", entry.key)
                return CommandOutcome(False, f"{entry.title} failed: {exc}")
        else:
            outcome = self._run_custom_arguments(entry, arguments)
        if outcome.success:
            self.db.add_history("command", entry.title)
        return outcome

    def preview_chain(self, expression: str):
        """Resolve a command chain without running anything and return a readable plan."""
        segments = split_command_chain(expression)
        if not segments or len(segments) > 10 or any(not part for part in segments):
            return False, "A command chain needs 1–10 non-empty steps separated by 'then'", []
        entries = self.entries()
        resolved = []
        lines = []
        for index, segment in enumerate(segments, 1):
            lowered = segment.casefold()
            matches = []
            for candidate in entries:
                for name in [candidate.key, candidate.title, *candidate.aliases]:
                    normalized = str(name).strip().casefold()
                    if normalized and (lowered == normalized or lowered.startswith(normalized + " ")):
                        matches.append((len(normalized), candidate, normalized))
            if not matches:
                return False, f"Step {index}: unknown command '{segment.split()[0]}'", []
            _length, entry, matched_name = max(matches, key=lambda item: item[0])
            args_text = segment[len(matched_name):].strip()
            marker = " (confirmation required)" if entry.confirmation else ""
            lines.append(f"{index}. {entry.title} {args_text}{marker}".rstrip())
            resolved.append((entry, args_text))
        return True, "", (lines, resolved)

    def run_chain(self, expression: str) -> CommandOutcome:
        """Run a bounded chain of named commands; no shell syntax is interpreted."""
        ok, message, plan = self.preview_chain(expression)
        if not ok:
            return CommandOutcome(False, message)
        _lines, resolved = plan
        completed: list[str] = []
        for index, (entry, args_text) in enumerate(resolved, 1):
            if entry.confirmation:
                if not self.hooks.confirm(
                    f"Confirm chain step: {entry.title}",
                    f"Run this step?\\n\\n{entry.description}\\n\\n"
                    f"Step {index} of {len(resolved)}. The chain stops if a step fails.",
                ):
                    return CommandOutcome(False, f"Chain cancelled at step {index}")
            outcome = self.run(entry, args_text)
            if not outcome.success:
                return CommandOutcome(False, f"Step {index} ({entry.title}) failed: {outcome.message}",
                                      "\\n".join(completed))
            completed.append(outcome.message or entry.title)
        return CommandOutcome(True, f"Completed {len(completed)} command-chain steps",
                              "\\n".join(completed))


    def _run_custom(self, entry: CommandEntry, args_text: str) -> CommandOutcome:
        return self._run_custom_arguments(entry, util.split_args(args_text))

    def _run_custom_arguments(self, entry: CommandEntry, extra: list[str]) -> CommandOutcome:
        command = str(entry.raw.get("command", "")).strip()
        if not command:
            return CommandOutcome(False, "The command has no executable")
        resolved = self._resolve_executable(command)
        if resolved is None:
            return CommandOutcome(False, f"Executable not found: {command}")
        template = str(entry.raw.get("args", "") or "")
        arguments = util.split_args(template)
        if "{args}" in arguments:
            index = arguments.index("{args}")
            arguments = arguments[:index] + extra + arguments[index + 1 :]
        elif extra:
            arguments.extend(extra)
        return self._detached([resolved, *arguments], f"Started {entry.title}")

    @staticmethod
    def _resolve_executable(command: str) -> str | None:
        candidate = Path(command).expanduser()
        if candidate.exists() and candidate.is_file():
            return str(candidate)
        return util.which(command)

    # ---------------------------------------------------------------- helpers
    def _detached(self, args: list[str], message: str) -> CommandOutcome:
        ok, detail = util.run_detached(args)
        return CommandOutcome(ok, message if ok else detail)

    def _capture(self, args: list[str], timeout: float = 20.0) -> CommandOutcome:
        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
                creationflags=util.hidden_process_flags(),
                check=False,
            )
        except FileNotFoundError:
            return CommandOutcome(False, f"{args[0]} is not available on this system")
        except subprocess.TimeoutExpired:
            return CommandOutcome(False, f"{args[0]} did not finish in time")
        except OSError as exc:
            return CommandOutcome(False, f"Could not run {args[0]}: {exc}")
        output = (completed.stdout or "").strip()
        error = (completed.stderr or "").strip()
        combined = "\n".join(part for part in (output, error) if part)
        if completed.returncode != 0 and not output:
            return CommandOutcome(False, error or f"{args[0]} exited with code {completed.returncode}")
        return CommandOutcome(True, f"{args[0]} finished", combined)

    @staticmethod
    def _unsupported(feature: str) -> CommandOutcome:
        platform_name = "Windows" if os.name == "nt" else sys.platform
        return CommandOutcome(False, f"{feature} is not supported on {platform_name}")

    # --------------------------------------------------------------- built-ins
    def _shutdown(self, args: list[str]) -> CommandOutcome:
        if os.name != "nt":
            return self._unsupported("Shutting down")
        return self._detached(["shutdown.exe", "/s", "/t", "0"], "Shutting down…")

    def _restart(self, args: list[str]) -> CommandOutcome:
        if os.name != "nt":
            return self._unsupported("Restarting")
        return self._detached(["shutdown.exe", "/r", "/t", "0"], "Restarting…")

    def _sleep(self, args: list[str]) -> CommandOutcome:
        if os.name == "nt":
            try:
                import ctypes

                # SetSuspendState(hibernate=False, force=False, wake=False)
                # sleeps on normal Windows configurations and needs no shell.
                if ctypes.windll.powrprof.SetSuspendState(False, False, False):
                    return CommandOutcome(True, "Suspending…")
                log.info("SetSuspendState returned false; falling back to rundll32")
            except Exception:
                log.debug("SetSuspendState unavailable", exc_info=True)
            return self._detached(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], "Suspending…"
            )
        if util.which("systemctl"):
            return self._detached(["systemctl", "suspend"], "Suspending…")
        return self._unsupported("Sleep")

    def _lock(self, args: list[str]) -> CommandOutcome:
        if os.name == "nt":
            try:
                import ctypes

                if ctypes.windll.user32.LockWorkStation():
                    return CommandOutcome(True, "Session locked")
            except Exception:
                log.debug("LockWorkStation unavailable", exc_info=True)
            return self._detached(["rundll32.exe", "user32.dll,LockWorkStation"], "Session locked")
        if util.which("loginctl"):
            return self._detached(["loginctl", "lock-session"], "Session locked")
        return self._unsupported("Locking the session")

    def _settings(self, args: list[str]) -> CommandOutcome:
        if os.name != "nt":
            return self._unsupported("Windows Settings")
        try:
            os.startfile("ms-settings:")  # type: ignore[attr-defined]
            return CommandOutcome(True, "Opened Windows Settings")
        except OSError as exc:
            return CommandOutcome(False, f"Could not open Windows Settings: {exc}")

    def _taskmgr(self, args: list[str]) -> CommandOutcome:
        if os.name == "nt":
            return self._detached(["taskmgr.exe"], "Opened Task Manager")
        for candidate in ("gnome-system-monitor", "ksysguard", "plasma-systemmonitor"):
            if util.which(candidate):
                return self._detached([candidate], "Opened the system monitor")
        return self._unsupported("Task Manager")

    def _terminal(self, args: list[str]) -> CommandOutcome:
        if os.name == "nt":
            if util.which("wt.exe"):
                return self._detached(["wt.exe"], "Opened Windows Terminal")
            shell = util.which("powershell.exe") or "powershell.exe"
            return self._detached([shell], "Opened PowerShell")
        for candidate in ("x-terminal-emulator", "gnome-terminal", "konsole", "alacritty", "xterm"):
            if util.which(candidate):
                return self._detached([candidate], "Opened a terminal")
        return CommandOutcome(False, "No terminal emulator was found")

    def _explorer(self, args: list[str]) -> CommandOutcome:
        target = args[0] if args else ""
        if os.name == "nt":
            if target:
                path = Path(target).expanduser()
                if not path.exists():
                    return CommandOutcome(False, f"Folder does not exist: {target}")
                return self._detached(["explorer.exe", str(path)], "Opened File Explorer")
            return self._detached(["explorer.exe"], "Opened File Explorer")
        directory = target or str(Path.home())
        ok, message = util.open_path_platform(directory)
        return CommandOutcome(ok, message)

    def _ipconfig(self, args: list[str]) -> CommandOutcome:
        if os.name == "nt":
            return self._capture(["ipconfig", "/all"])
        if util.which("ip"):
            return self._capture(["ip", "address"])
        return self._capture(["hostname", "-I"])

    def _empty_recycle(self, args: list[str]) -> CommandOutcome:
        if os.name != "nt":
            return self._unsupported("Emptying the Recycle Bin")
        outcome = self._capture(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "Clear-RecycleBin -Force -ErrorAction Stop",
            ],
            timeout=60,
        )
        if not outcome.success and "empty" in outcome.message.lower():
            return CommandOutcome(True, "The Recycle Bin was already empty")
        return outcome

    # -------------------------------------------------------------- validation
    def validate_custom(self, data: dict) -> tuple[bool, str]:
        name = str(data.get("name", "")).strip()
        command = str(data.get("command", "")).strip()
        if not name:
            return False, "A name is required"
        if not command:
            return False, "An executable is required"
        if self._resolve_executable(command) is None:
            return False, f"Executable not found: {command}"
        if "\n" in command:
            return False, "The executable path must be a single line"
        return True, ""

    def save_custom(self, data: dict) -> tuple[bool, str]:
        ok, message = self.validate_custom(data)
        if not ok:
            return False, message
        result = self.db.upsert_custom_command(data)
        if result < 0:
            return False, "Could not save the command"
        return True, ""

    def delete_custom(self, command_id: int) -> None:
        self.db.delete_custom_command(command_id)

    def history(self, limit: int = 20) -> list[str]:
        return [row["value"] for row in self.db.history("command", limit)]


class CommandsProvider(SearchProvider):
    """The ``comm:`` keyword."""

    id = "commands"
    title = "Commands"
    keyword = "comm"
    weight = 1.0
    auto = False

    def __init__(self, config, db, hooks, service: CommandService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or CommandService(config, db, hooks)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip()
        if not text:
            return [self._result(entry, 0.8 - index * 0.02) for index, entry in enumerate(self.service.entries()[:limit])]
        entries = self.service.search(text, limit)
        if not entries:
            return [
                self.make_result(
                    title=f"No command matches “{text}”",
                    subtitle="Try comm: ipconfig or add a custom command in Settings → Commands",
                    category="Command",
                    score=0.6,
                    primary=lambda: self.hooks.open_settings("commands"),
                    icon_glyph=">",
                )
            ]
        return [self._result(entry, max(0.55, 0.95 - index * 0.03)) for index, entry in enumerate(entries)]

    def _result(self, entry: CommandEntry, score: float) -> SearchResult:
        details = entry.description
        if not entry.builtin:
            details = f"{details}  ·  {entry.raw.get('command', '')}"
        if self.service.needs_confirmation(entry):
            details += "  ·  asks for confirmation"
        actions = []
        if not entry.builtin:
            actions.append(
                ResultAction("Edit command", lambda: self.hooks.open_settings("commands"))
            )
        if entry.builtin and entry.key == "explorer":
            actions.append(ResultAction("Open home folder", lambda: self.hooks.open_path(str(Path.home()))))
        return self.make_result(
            title=entry.title,
            subtitle=details,
            category="Command",
            score=score,
            primary=lambda: self._execute(entry),
            actions=actions,
            copy_text=entry.title,
            icon_glyph=">",
            meta={"command": entry.key, "raw": entry.raw},
        )

    def _execute(self, entry: CommandEntry) -> None:
        if self.service.needs_confirmation(entry):
            confirmed = self.hooks.confirm(
                f"Run “{entry.title}”?",
                f"{entry.description}\n\nThis action cannot be undone.",
            )
            if not confirmed:
                self.hooks.notify("Command cancelled")
                return
        outcome = self.service.run(entry)
        if not outcome.success:
            self.hooks.show_error(entry.title, outcome.message)
            return
        if outcome.output:
            self.hooks.show_info(entry.title, outcome.output)
        else:
            self.hooks.notify(outcome.message or f"{entry.title} finished")
            self.hooks.hide_launcher()

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Commands",
            subtitle="Try: comm: ipconfig  ·  comm: taskmgr  ·  comm: empty recycle",
            category="Command",
            score=1.0,
            primary=lambda: self.hooks.open_settings("commands"),
            icon_glyph=">",
        )



class CommandChainProvider(SearchProvider):
    """Explicit chain: keyword for safe sequences of existing named commands."""

    id = "command_chains"
    title = "Command chains"
    keyword = "chain"
    weight = 1.0
    auto = False

    def __init__(self, config, db, hooks, service: CommandService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or CommandService(config, db, hooks)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        expression = (query or "").strip()
        if not expression:
            return [self.make_result(
                title="Command chains",
                subtitle="Use: chain: taskmgr then explorer",
                category="Command chain",
                score=1.0,
                primary=lambda: self.hooks.fill_query("chain: "),
                icon_glyph="⇢",
            )]
        step_count = len(split_command_chain(expression))
        return [self.make_result(
            title=f"Run {step_count} command steps",
            subtitle=expression,
            category="Command chain",
            score=1.0,
            primary=lambda: self._run(expression),
            icon_glyph="⇢",
        )]

    def _run(self, expression: str) -> None:
        outcome = self.service.run_chain(expression)
        if outcome.success:
            self.hooks.notify(outcome.message)
            self.hooks.hide_launcher()
        else:
            self.hooks.show_error("Command chain", outcome.message)


__all__ = ["CommandService", "CommandEntry", "CommandOutcome", "CommandsProvider", "CommandChainProvider", "split_command_chain"]
