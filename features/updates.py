"""Opt-in GitHub release checks; updates are downloaded only after user action."""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
import json
from typing import Any

from core.config_manager import ConfigManager
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider
from core.version import APP_VERSION
from core.workers import run_async

log = get_logger(__name__)
RELEASE_API = "https://api.github.com/repos/okyanus-11/SeekR/releases/latest"
RELEASE_PAGE = "https://github.com/okyanus-11/SeekR/releases/latest"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60


def version_key(value: str) -> tuple[int, ...]:
    numbers = [int(part) for part in re.findall(r"\d+", str(value))]
    return tuple(numbers or [0])


class UpdateService:
    def __init__(self, config: ConfigManager):
        self.config = config
        self.last_info: dict[str, Any] | None = None

    def check_due(self) -> bool:
        try:
            last = float(self.config.get("updates.last_check", 0) or 0)
        except (TypeError, ValueError):
            last = 0
        return time.time() - last >= CHECK_INTERVAL_SECONDS

    def check_latest(self) -> dict[str, Any]:
        request = urllib.request.Request(
            RELEASE_API,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "SeekR-update-check",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                payload = json.loads(response.read(512_000).decode("utf-8"))
        except (OSError, urllib.error.URLError, ValueError) as exc:
            log.warning("Update check failed: %s", exc)
            raise RuntimeError(f"Could not check for updates: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("GitHub returned an invalid release response")
        tag = str(payload.get("tag_name", "")).strip()
        latest = tag[1:] if tag.lower().startswith("v") else tag
        release_url = str(payload.get("html_url", RELEASE_PAGE))
        if not latest or not release_url.startswith("https://github.com/okyanus-11/SeekR/releases/"):
            raise RuntimeError("GitHub release metadata did not match the expected SeekR repository")
        info = {
            "current_version": APP_VERSION,
            "latest_version": latest,
            "release_url": release_url,
            "update_available": version_key(latest) > version_key(APP_VERSION),
            "assets": [
                {"name": str(asset.get("name", "")), "url": str(asset.get("browser_download_url", ""))}
                for asset in (payload.get("assets", []) or [])
                if isinstance(asset, dict)
            ],
            "checked_at": time.time(),
        }
        self.config.set("updates.last_check", info["checked_at"])
        self.last_info = info
        return info


class UpdateProvider(SearchProvider):
    id = "updates"
    title = "Updates"
    keyword = "update"
    weight = 0.8
    auto = False

    def __init__(self, config, db, hooks, service: UpdateService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or UpdateService(config)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        info = self.service.last_info
        subtitle = "Check the official SeekR GitHub release page for a newer version."
        actions = []
        if info:
            if info["update_available"]:
                subtitle = f"Version {info['latest_version']} is available (current {APP_VERSION})."
                actions.append(ResultAction("Open official release", lambda: self.hooks.open_url(info["release_url"])))
            else:
                subtitle = f"SeekR {APP_VERSION} is up to date (checked {time.strftime('%Y-%m-%d %H:%M', time.localtime(info['checked_at']))})."
        return [self.make_result(
            title="Check for updates",
            subtitle=subtitle,
            category="Updates",
            score=1.0,
            primary=self._check_async,
            actions=actions,
            icon_glyph="↻",
        )]

    def _check_async(self) -> None:
        run_async(
            self.service.check_latest,
            on_finished=self._completed,
            on_failed=self._failed,
        )

    def _completed(self, info: dict[str, Any]) -> None:
        if info["update_available"]:
            self.hooks.notify(
                f"SeekR {info['latest_version']} is available. Search update: to open the release.",
                "info",
            )
        else:
            self.hooks.notify(f"SeekR {APP_VERSION} is up to date.")

    def _failed(self, message: str, _traceback_text: str) -> None:
        self.hooks.notify(message, "warning")

    def empty_help(self) -> SearchResult | None:
        return self.search("", 1)[0]


__all__ = ["UpdateService", "UpdateProvider", "version_key", "RELEASE_PAGE"]
