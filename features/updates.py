"""Opt-in GitHub release checks; updates are downloaded only after user action."""
from __future__ import annotations

import hashlib
import hmac
import re
import time
import urllib.error
import urllib.request
import json
from pathlib import Path
from urllib.parse import urlsplit
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
MAX_UPDATE_ASSET_BYTES = 1_000_000_000
_VERSION_RE = re.compile(
    r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$",
    re.IGNORECASE,
)


def _is_official_release_page_url(value: str) -> bool:
    parsed = urlsplit(str(value).strip())
    return (
        parsed.scheme == "https"
        and parsed.netloc == "github.com"
        and parsed.path.startswith("/okyanus-11/SeekR/releases/")
        and not parsed.query
        and not parsed.fragment
    )


def _is_official_asset_url(value: str) -> bool:
    parsed = urlsplit(str(value).strip())
    return (
        parsed.scheme == "https"
        and parsed.netloc == "github.com"
        and parsed.path.startswith("/okyanus-11/SeekR/releases/download/")
        and not parsed.query
        and not parsed.fragment
    )


def version_key(value: str) -> tuple:
    """Return a SemVer-like key; a final release sorts after its prereleases."""
    match = _VERSION_RE.fullmatch(str(value).strip())
    if not match:
        numbers = [int(part) for part in re.findall(r"\d+", str(value))]
        return tuple(numbers or [0])
    base = tuple(int(match.group(index)) for index in (1, 2, 3))
    prerelease = match.group(4)
    if prerelease is None:
        return base + (1,)
    identifiers = tuple(
        (0, int(part)) if part.isdigit() else (1, part.lower())
        for part in prerelease.split(".")
    )
    return base + (0, identifiers)


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

    @staticmethod
    def verify_asset_file(asset: dict[str, Any], file_path: str | Path) -> tuple[bool, str]:
        """Verify a user-downloaded file against trusted GitHub release metadata."""
        if not isinstance(asset, dict):
            return False, "Invalid release asset metadata"
        name = str(asset.get("name", "")).strip()
        url = str(asset.get("url", "")).strip()
        expected = str(asset.get("sha256", "")).strip().lower()
        if (not name
                or not _is_official_asset_url(url)
                or not re.fullmatch(r"[0-9a-f]{64}", expected)):
            return False, "The release asset does not include trusted SHA-256 metadata"
        path = Path(file_path).expanduser()
        try:
            if not path.is_file():
                return False, "The selected file does not exist"
            actual_size = path.stat().st_size
            expected_size = int(asset.get("size", 0) or 0)
            if expected_size <= 0 or expected_size > MAX_UPDATE_ASSET_BYTES:
                return False, f"Invalid expected file size for {name}"
            if actual_size > MAX_UPDATE_ASSET_BYTES or actual_size != expected_size:
                return False, f"File size mismatch for {name}"
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if not hmac.compare_digest(digest.hexdigest(), expected):
                return False, f"SHA-256 mismatch for {name}"
            return True, f"SHA-256 verified for {name}"
        except (OSError, TypeError, ValueError) as exc:
            log.warning("Could not verify downloaded update asset: %s", exc)
            return False, f"Could not verify the selected file: {exc}"

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
        if not _VERSION_RE.fullmatch(latest):
            raise RuntimeError("GitHub returned an invalid SeekR release version")
        release_url = str(payload.get("html_url", RELEASE_PAGE))
        if not latest or not _is_official_release_page_url(release_url):
            raise RuntimeError("GitHub release metadata did not match the expected SeekR repository")
        assets = []
        for asset in payload.get("assets", []) or []:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", "")).strip()
            url = str(asset.get("browser_download_url", "")).strip()
            digest = str(asset.get("digest", "")).strip().lower()
            # Only expose assets hosted by the official repository and hashes
            # supplied by GitHub in its documented sha256:<hex> format.
            if (not name or not _is_official_asset_url(url)
                    or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest)):
                continue
            try:
                size = max(0, int(asset.get("size", 0)))
            except (TypeError, ValueError):
                size = 0
            if size <= 0:
                continue
            assets.append({
                "name": name,
                "url": url,
                "sha256": digest.split(":", 1)[1],
                "size": size,
            })
        info = {
            "current_version": APP_VERSION,
            "latest_version": latest,
            "release_url": release_url,
            "update_available": version_key(latest) > version_key(APP_VERSION),
            "assets": assets,
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
                for asset in info.get("assets", []):
                    name = asset["name"]
                    url = asset["url"]
                    digest = asset["sha256"]
                    actions.append(ResultAction(
                        f"Download {name}",
                        lambda url=url: self.hooks.open_url(url),
                    ))
                    actions.append(ResultAction(
                        f"Copy SHA-256 · {name}",
                        lambda digest=digest: self.hooks.copy_text(digest),
                    ))
                    actions.append(ResultAction(
                        f"Verify downloaded {name}…",
                        lambda asset=asset: self.hooks.verify_update_asset(asset),
                    ))
                if info.get("assets"):
                    subtitle += f" SHA-256 hashes are available for {len(info['assets'])} verified official asset metadata entr{'y' if len(info['assets']) == 1 else 'ies'}."
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
