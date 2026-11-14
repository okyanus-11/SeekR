"""Process inspection and safe termination."""

from __future__ import annotations

import time
from typing import Any

import psutil

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import fuzzy_score
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

from . import util

log = get_logger(__name__)

_CACHE: dict[int, psutil.Process] = {}


def list_processes(limit: int | None = None) -> list[dict[str, Any]]:
    """Return running processes with live CPU and memory figures."""
    processes: list[dict[str, Any]] = []
    alive: set[int] = set()
    try:
        iterator = psutil.process_iter(
            ["pid", "name", "username", "status", "memory_info", "create_time", "exe"]
        )
    except Exception as exc:  # pragma: no cover - psutil availability
        log.warning("Could not enumerate processes: %s", exc)
        return []
    for proc in iterator:
        pid = proc.info.get("pid")
        if not pid:
            continue
        alive.add(pid)
        cached = _CACHE.get(pid)
        if cached is None:
            cached = proc
            _CACHE[pid] = cached
            try:
                cached.cpu_percent(None)  # prime the sampler
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        try:
            cpu = cached.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            cpu = None
        memory = proc.info.get("memory_info")
        processes.append(
            {
                "pid": pid,
                "name": proc.info.get("name") or f"PID {pid}",
                "user": proc.info.get("username") or "",
                "status": proc.info.get("status") or "",
                "cpu": cpu or 0.0,
                "memory": getattr(memory, "rss", 0) if memory else 0,
                "exe": proc.info.get("exe") or "",
                "created": proc.info.get("create_time") or 0.0,
            }
        )
    for dead in set(_CACHE) - alive:
        _CACHE.pop(dead, None)
    processes.sort(key=lambda item: item["memory"], reverse=True)
    return processes[:limit] if limit else processes


def process_details(pid: int) -> dict[str, Any] | None:
    try:
        proc = psutil.Process(pid)
        with proc.oneshot():
            memory = proc.memory_info()
            return {
                "pid": pid,
                "name": proc.name(),
                "exe": proc.exe() if proc.exe() else "",
                "cmdline": proc.cmdline(),
                "user": proc.username(),
                "status": proc.status(),
                "cpu": proc.cpu_percent(None),
                "memory": memory.rss,
                "threads": proc.num_threads(),
                "created": proc.create_time(),
                "cwd": proc.cwd() if hasattr(proc, "cwd") else "",
            }
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, OSError) as exc:
        log.info("Process details unavailable for %s: %s", pid, exc)
        return None


def terminate_process(pid: int, force: bool = False) -> tuple[bool, str]:
    """Terminate a process, reporting permission problems clearly."""
    if pid in (0, 1, 4):
        return False, "This system process cannot be terminated"
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except psutil.TimeoutExpired:
            if force:
                proc.kill()
                proc.wait(timeout=2)
            else:
                return False, f"{name} did not exit yet; try again with force"
        _CACHE.pop(pid, None)
        return True, f"Terminated {name} (PID {pid})"
    except psutil.NoSuchProcess:
        return False, f"PID {pid} is no longer running"
    except psutil.AccessDenied:
        return False, "Access denied. Run SeekR as administrator to terminate this process."
    except Exception as exc:
        log.exception("Could not terminate PID %s", pid)
        return False, f"Could not terminate the process: {exc}"


class ProcessProvider(SearchProvider):
    """The ``ps`` keyword."""

    id = "processes"
    title = "Processes"
    keyword = "ps"
    weight = 0.85
    auto = False

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip()
        processes = list_processes()
        if text:
            scored = []
            for process in processes:
                score = fuzzy_score(text, process["name"], typo_tolerance=True)
                if score <= 0:
                    continue
                scored.append((score, process))
            scored.sort(key=lambda pair: pair[0], reverse=True)
            processes = [process for _, process in scored[:limit]]
        else:
            processes = processes[:limit]
        if not processes:
            return [
                self.make_result(
                    title="No matching processes",
                    subtitle="Type the beginning of a process name",
                    category="Process",
                    score=0.7,
                    primary=lambda: self.hooks.open_tools("processes"),
                    icon_glyph="▤",
                )
            ]
        return [self._result(process, 0.9 - index * 0.02) for index, process in enumerate(processes)]

    def _result(self, process: dict, score: float) -> SearchResult:
        subtitle = (
            f"PID {process['pid']}  ·  CPU {process['cpu']:.1f}%  ·  "
            f"RAM {util.format_bytes(process['memory'])}  ·  {process['status']}"
        )
        return self.make_result(
            title=process["name"],
            subtitle=subtitle,
            category="Process",
            score=score,
            primary=lambda: self.hooks.open_tools("processes"),
            actions=[
                ResultAction("Terminate process…", lambda: self._terminate(process)),
                ResultAction("Copy PID", lambda: self.hooks.copy_text(str(process["pid"]))),
                ResultAction(
                    "Open file location",
                    lambda: self.hooks.reveal_path(process["exe"]) if process["exe"] else self.hooks.notify("Executable path unavailable"),
                ),
            ],
            copy_text=str(process["pid"]),
            icon_glyph="▤",
            meta={"process": process},
        )

    def _terminate(self, process: dict) -> None:
        if not self.hooks.confirm(
            f"Terminate {process['name']}?",
            f"PID {process['pid']} will be terminated. Unsaved work in that program may be lost.",
        ):
            return
        ok, message = terminate_process(int(process["pid"]))
        self.hooks.notify(message, "info" if ok else "error")

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Process manager",
            subtitle="Search running processes, inspect resource usage and terminate them",
            category="Process",
            score=1.0,
            primary=lambda: self.hooks.open_tools("processes"),
            icon_glyph="▤",
        )


__all__ = ["list_processes", "process_details", "terminate_process", "ProcessProvider"]
