"""Live system information collected from the operating system."""

from __future__ import annotations

import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from typing import Any

import psutil

from core.config_manager import ConfigManager
from core.database import Database
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

from . import util

log = get_logger(__name__)

# Prime psutil's CPU sampling so the first snapshot is meaningful.
try:  # pragma: no cover - depends on the machine
    psutil.cpu_percent(interval=None)
except Exception:
    pass


def cpu_info() -> dict[str, Any]:
    try:
        physical = psutil.cpu_count(logical=False)
        logical = psutil.cpu_count(logical=True)
        # interval=None never blocks: the module-level priming call makes the
        # first reading meaningful and later calls report since-last-call use.
        percent = psutil.cpu_percent(interval=None)
        frequency = None
        with_freq = psutil.cpu_freq()
        if with_freq is not None:
            frequency = with_freq.current
        return {
            "percent": percent,
            "physical": physical,
            "logical": logical,
            "frequency_mhz": frequency,
            "load": os.getloadavg() if hasattr(os, "getloadavg") else None,
        }
    except Exception as exc:
        log.warning("CPU information unavailable: %s", exc)
        return {"percent": None, "physical": None, "logical": None, "frequency_mhz": None, "load": None}


def memory_info() -> dict[str, Any]:
    try:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total": vm.total,
            "used": vm.used,
            "available": vm.available,
            "percent": vm.percent,
            "swap_total": swap.total,
            "swap_used": swap.used,
            "swap_percent": swap.percent,
        }
    except Exception as exc:
        log.warning("Memory information unavailable: %s", exc)
        return {"total": None, "used": None, "available": None, "percent": None}


def disk_info() -> list[dict[str, Any]]:
    disks: list[dict[str, Any]] = []
    try:
        for partition in psutil.disk_partitions(all=False):
            if "cdrom" in getattr(partition, "opts", "") or not partition.fstype:
                continue
            try:
                usage = psutil.disk_usage(partition.mountpoint)
            except OSError:
                continue
            disks.append(
                {
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent,
                }
            )
    except Exception as exc:
        log.warning("Disk information unavailable: %s", exc)
    return disks


def battery_info() -> dict[str, Any] | None:
    try:
        battery = psutil.sensors_battery()
    except Exception:
        return None
    if battery is None:
        return None
    return {
        "percent": battery.percent,
        "plugged": battery.power_plugged,
        "seconds_left": battery.secsleft if battery.secsleft not in (-1, -2) else None,
    }


def network_info() -> dict[str, Any]:
    info: dict[str, Any] = {"hostname": "", "ip": None, "interfaces": [], "connected": False}
    try:
        info["hostname"] = socket.gethostname()
    except OSError:
        pass
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        for name, stat in stats.items():
            if not stat.isup:
                continue
            addresses = [
                address.address
                for address in addrs.get(name, [])
                if address.family == socket.AF_INET and not address.address.startswith("127.")
            ]
            info["interfaces"].append({"name": name, "speed": stat.speed, "addresses": addresses})
    except Exception:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.settimeout(0.3)
            probe.connect(("8.8.8.8", 80))
            info["ip"] = probe.getsockname()[0]
            info["connected"] = True
    except OSError:
        for interface in info["interfaces"]:
            if interface["addresses"]:
                info["ip"] = interface["addresses"][0]
                info["connected"] = True
                break
    return info


def uptime_seconds() -> float | None:
    try:
        return max(0.0, time.time() - psutil.boot_time())
    except Exception:
        return None


def os_info() -> dict[str, Any]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "boot_time": psutil.boot_time(),
    }


def _run_quiet(args: list[str], timeout: float = 8.0, encoding: str | None = None) -> str:
    options: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "errors": "replace",
        "timeout": timeout,
        "creationflags": util.hidden_process_flags(),
        "check": False,
    }
    if encoding:
        options["encoding"] = encoding
    try:
        completed = subprocess.run(args, **options)
        return (completed.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _nvidia_smi_gpus() -> list[dict[str, Any]]:
    if shutil.which("nvidia-smi") is None:
        return []
    output = _run_quiet(
        [
            "nvidia-smi",
            "--query-gpu=name,utilization.gpu,memory.used,memory.total",
            "--format=csv,noheader,nounits",
        ]
    )
    gpus = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 4:
            continue
        try:
            used = float(parts[2])
            total = float(parts[3])
        except ValueError:
            used = total = 0.0
        gpus.append(
            {
                "name": parts[0],
                "utilization": float(parts[1]) if parts[1].replace(".", "", 1).isdigit() else None,
                "memory_used": used * 1024 * 1024 if used else None,
                "memory_total": total * 1024 * 1024 if total else None,
                "driver": None,
            }
        )
    return gpus


def _windows_gpus() -> list[dict[str, Any]]:
    output = _run_quiet(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "Get-CimInstance Win32_VideoController | "
            "Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress",
        ],
        timeout=10,
        encoding="utf-8",
    )
    if not output:
        return []
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        payload = [payload]
    gpus = []
    for item in payload:
        memory = item.get("AdapterRAM")
        try:
            memory_value = int(memory) if memory else None
        except (TypeError, ValueError):
            memory_value = None
        gpus.append(
            {
                "name": item.get("Name") or "GPU",
                "utilization": None,
                "memory_used": None,
                "memory_total": memory_value if memory_value and memory_value > 0 else None,
                "driver": item.get("DriverVersion"),
            }
        )
    return gpus


def _linux_gpus() -> list[dict[str, Any]]:
    gpus = _nvidia_smi_gpus()
    if gpus:
        return gpus
    if shutil.which("lspci") is None:
        return []
    output = _run_quiet(["lspci"])
    found = []
    for line in output.splitlines():
        if any(keyword in line for keyword in ("VGA compatible controller", "3D controller", "Display controller")):
            name = line.split(":", 2)[-1].strip()
            found.append(
                {
                    "name": name,
                    "utilization": None,
                    "memory_used": None,
                    "memory_total": None,
                    "driver": None,
                }
            )
    return found


_GPU_TTL_SECONDS = 30.0
_gpu_lock = threading.Lock()
_gpu_cache: dict[str, Any] = {"value": [], "loaded_at": 0.0, "loading": False}


def _collect_gpus() -> list[dict[str, Any]]:
    if os.name == "nt":
        gpus = _windows_gpus()
        usage = {gpu["name"].lower(): gpu for gpu in _nvidia_smi_gpus()}
        for gpu in gpus:
            match = usage.get(gpu["name"].lower())
            if match:
                gpu["utilization"] = match["utilization"]
                gpu["memory_used"] = match["memory_used"]
                gpu["memory_total"] = gpu["memory_total"] or match["memory_total"]
        return gpus
    if sys.platform.startswith("linux"):
        return _linux_gpus()
    return []


def gpu_info() -> list[dict[str, Any]]:
    """Return cached GPU data and refresh it in the background.

    Querying Windows GPUs shells out to PowerShell/WMI, which can take
    seconds. The search UI must never wait for that, so the first call returns
    the previous snapshot (possibly empty) and a daemon thread refreshes it.
    """
    now = time.time()
    with _gpu_lock:
        snapshot = [dict(item) for item in _gpu_cache["value"]]
        fresh = now - float(_gpu_cache["loaded_at"]) < _GPU_TTL_SECONDS
        if fresh or _gpu_cache["loading"]:
            return snapshot
        _gpu_cache["loading"] = True

    def refresh() -> None:
        try:
            value = _collect_gpus()
        except Exception as exc:  # pragma: no cover - platform dependent
            log.warning("GPU information unavailable: %s", exc)
            value = []
        with _gpu_lock:
            _gpu_cache["value"] = value
            _gpu_cache["loaded_at"] = time.time()
            _gpu_cache["loading"] = False

    threading.Thread(target=refresh, name="seekr-gpu-info", daemon=True).start()
    return snapshot


def warm_up() -> None:
    """Start the GPU probe without blocking the caller."""
    gpu_info()


def snapshot() -> dict[str, Any]:
    """Collect a full system snapshot; unavailable values are ``None``."""
    return {
        "cpu": cpu_info(),
        "memory": memory_info(),
        "disks": disk_info(),
        "battery": battery_info(),
        "network": network_info(),
        "uptime": uptime_seconds(),
        "os": os_info(),
        "gpu": gpu_info(),
        "collected_at": time.time(),
    }


class SystemInfoProvider(SearchProvider):
    """The ``sys:`` keyword."""

    id = "system"
    title = "System information"
    keyword = "sys"
    weight = 1.0
    auto = False

    def search(self, query: str, limit: int) -> list[SearchResult]:
        data = snapshot()
        results: list[SearchResult] = []

        cpu = data["cpu"]
        if cpu.get("percent") is not None:
            title = f"CPU  {cpu['percent']:.1f}%  ·  {cpu.get('logical') or '?'} threads"
            subtitle = (
                f"{cpu.get('physical') or '?'} cores"
                + (f"  ·  {cpu['frequency_mhz']:.0f} MHz" if cpu.get("frequency_mhz") else "")
            )
            results.append(self._row(title, subtitle, "cpu", f"CPU usage: {cpu['percent']:.1f}%"))

        memory = data["memory"]
        if memory.get("percent") is not None:
            results.append(
                self._row(
                    f"RAM  {memory['percent']:.1f}%  ·  {util.format_bytes(memory['used'])} used",
                    f"{util.format_bytes(memory['total'])} total  ·  {util.format_bytes(memory['available'])} available",
                    "memory",
                    f"RAM usage: {memory['percent']:.1f}% ({util.format_bytes(memory['used'])} / {util.format_bytes(memory['total'])})",
                )
            )

        for disk in data["disks"]:
            results.append(
                self._row(
                    f"Disk {disk['mountpoint']}  {disk['percent']:.0f}% used",
                    f"{util.format_bytes(disk['used'])} of {util.format_bytes(disk['total'])}  ·  {disk['fstype']}",
                    "disk",
                    f"{disk['mountpoint']}: {util.format_bytes(disk['used'])} / {util.format_bytes(disk['total'])}",
                )
            )

        battery = data["battery"]
        if battery:
            state = "plugged in" if battery["plugged"] else "on battery"
            remaining = (
                f"  ·  {util.format_duration(battery['seconds_left'])} remaining"
                if battery.get("seconds_left")
                else ""
            )
            results.append(
                self._row(
                    f"Battery  {battery['percent']:.0f}%  ·  {state}",
                    f"Battery status{remaining}",
                    "battery",
                    f"Battery: {battery['percent']:.0f}% ({state})",
                )
            )

        network = data["network"]
        if network.get("ip"):
            results.append(
                self._row(
                    f"Network  {network['ip']}",
                    f"Host {network['hostname']}  ·  {len(network['interfaces'])} active interfaces",
                    "network",
                    network["ip"] or "",
                )
            )

        for gpu in data["gpu"]:
            title = f"GPU  {gpu['name']}"
            subtitle_parts = []
            if gpu.get("utilization") is not None:
                subtitle_parts.append(f"{gpu['utilization']:.0f}% utilisation")
            if gpu.get("memory_total"):
                subtitle_parts.append(f"{util.format_bytes(gpu['memory_total'])} memory")
            if gpu.get("driver"):
                subtitle_parts.append(f"driver {gpu['driver']}")
            results.append(self._row(title, "  ·  ".join(subtitle_parts) or "GPU detected", "gpu", gpu["name"]))

        if data["uptime"] is not None:
            results.append(
                self._row(
                    f"Uptime  {util.format_duration(data['uptime'])}",
                    f"Started {time.strftime('%Y-%m-%d %H:%M', time.localtime(data['os']['boot_time']))}",
                    "uptime",
                    util.format_duration(data["uptime"]),
                )
            )

        os_data = data["os"]
        results.append(
            self._row(
                f"{os_data['system']} {os_data['release']}",
                f"{os_data['machine']}  ·  Python {os_data['python']}",
                "system",
                f"{os_data['system']} {os_data['release']} ({os_data['version']})",
            )
        )

        wanted = (query or "").strip().lower()
        if wanted:
            results = [
                item for item in results if wanted in item.title.lower() or wanted in item.subtitle.lower()
            ]
        for index, result in enumerate(results):
            result.score = 0.95 - index * 0.02
        return results[:limit]

    def _row(self, title: str, subtitle: str, kind: str, copy_value: str) -> SearchResult:
        return self.make_result(
            title=title,
            subtitle=subtitle,
            category="System",
            score=0.9,
            primary=lambda: self.hooks.copy_text(copy_value),
            actions=[
                ResultAction("Open system information", lambda: self.hooks.open_tools("system")),
                ResultAction("Refresh system information", lambda: self.hooks.fill_query("sys:")),
            ],
            copy_text=copy_value,
            icon_glyph={"cpu": "▤", "memory": "▥", "disk": "▣", "battery": "▮", "network": "⌁", "gpu": "▦"}.get(kind, "▤"),
            meta={"kind": kind},
        )

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="System information",
            subtitle="Show live CPU, memory, disk, battery, GPU and network details",
            category="System",
            score=1.0,
            primary=lambda: self.hooks.open_tools("system"),
            icon_glyph="▤",
        )


__all__ = [
    "snapshot",
    "cpu_info",
    "memory_info",
    "disk_info",
    "battery_info",
    "network_info",
    "uptime_seconds",
    "os_info",
    "gpu_info",
    "warm_up",
    "SystemInfoProvider",
]
