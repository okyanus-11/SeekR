"""Date and time utilities."""

from __future__ import annotations

import datetime as dt
import re
from functools import lru_cache
from typing import Any

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import similarity
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

try:  # Python 3.9+ standard library, tzdata on Windows
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore[assignment]
    ZoneInfoNotFoundError = Exception  # type: ignore[assignment]
    available_timezones = lambda: set()  # type: ignore[assignment]

log = get_logger(__name__)


class TimeZoneError(ValueError):
    """Raised when a time zone cannot be resolved."""


@lru_cache(maxsize=1)
def zone_names() -> tuple[str, ...]:
    try:
        return tuple(sorted(available_timezones()))
    except Exception:  # pragma: no cover - platform dependent
        return ("UTC",)


def resolve_zone(name: str) -> ZoneInfo:
    cleaned = (name or "").strip()
    if not cleaned:
        cleaned = "UTC"
    if cleaned.lower() in {"local", "system"}:
        local_tz = dt.datetime.now().astimezone().tzinfo
        if isinstance(local_tz, ZoneInfo):
            return local_tz
        local_tz = local_tz or dt.timezone.utc
        return local_tz  # type: ignore[return-value]
    aliases = {
        "utc": "UTC",
        "gmt": "Etc/GMT",
        "istanbul": "Europe/Istanbul",
        "ankara": "Europe/Istanbul",
        "turkey": "Europe/Istanbul",
        "london": "Europe/London",
        "paris": "Europe/Paris",
        "berlin": "Europe/Berlin",
        "tokyo": "Asia/Tokyo",
        "beijing": "Asia/Shanghai",
        "shanghai": "Asia/Shanghai",
        "newyork": "America/New_York",
        "new york": "America/New_York",
        "losangeles": "America/Los_Angeles",
        "los angeles": "America/Los_Angeles",
        "chicago": "America/Chicago",
        "sydney": "Australia/Sydney",
        "moscow": "Europe/Moscow",
        "dubai": "Asia/Dubai",
        "singapore": "Asia/Singapore",
        "hongkong": "Asia/Hong_Kong",
        "hong kong": "Asia/Hong_Kong",
        "toronto": "America/Toronto",
        "saopaulo": "America/Sao_Paulo",
        "sao paulo": "America/Sao_Paulo",
        "cairo": "Africa/Cairo",
        "cape town": "Africa/Johannesburg",
    }
    key = cleaned.lower().replace("_", " ").replace("-", " ")
    key_compact = key.replace(" ", "")
    if key_compact in aliases:
        cleaned = aliases[key_compact]
    # Case-insensitive match against the IANA database.
    for candidate in zone_names():
        if candidate.lower() == cleaned.lower():
            return ZoneInfo(candidate)
    match = find_zone(cleaned)
    if match:
        return ZoneInfo(match)
    raise TimeZoneError(f"Unknown time zone: {name}")


def find_zone(query: str) -> str | None:
    """Find the best matching IANA zone for a free-form city name."""
    text = (query or "").strip()
    if not text:
        return None
    lowered = text.lower()
    names = zone_names()
    for candidate in names:
        if candidate.lower() == lowered:
            return candidate
    mapped = resolve_alias(lowered)
    if mapped:
        return mapped
    matches = [name for name in names if name.lower().endswith("/" + lowered)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        return sorted(matches, key=len)[0]
    partial = [name for name in names if lowered in name.lower().replace("_", " ")]
    if len(partial) == 1:
        return partial[0]
    if partial:
        return sorted(partial, key=len)[0]
    scored: list[tuple[float, str]] = []
    for name in names:
        city = name.split("/")[-1].replace("_", " ").lower()
        score = similarity(lowered, city)
        if score >= 0.75:
            scored.append((score, name))
    if scored:
        scored.sort(reverse=True)
        return scored[0][1]
    return None


def resolve_alias(lowered: str) -> str | None:
    alias_map = {
        "utc": "UTC", "gmt": "Etc/GMT", "istanbul": "Europe/Istanbul",
        "ankara": "Europe/Istanbul", "turkey": "Europe/Istanbul",
        "tokyo": "Asia/Tokyo", "london": "Europe/London", "paris": "Europe/Paris",
        "berlin": "Europe/Berlin", "new york": "America/New_York",
        "newyork": "America/New_York", "los angeles": "America/Los_Angeles",
        "losangeles": "America/Los_Angeles", "sydney": "Australia/Sydney",
        "moscow": "Europe/Moscow", "dubai": "Asia/Dubai", "singapore": "Asia/Singapore",
    }
    return alias_map.get(lowered)


def now(zone_name: str | None = None) -> dt.datetime:
    if zone_name:
        return dt.datetime.now(resolve_zone(zone_name))
    return dt.datetime.now().astimezone()


def format_datetime(moment: dt.datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return moment.strftime(fmt)


def utc_offset(moment: dt.datetime) -> str:
    offset = moment.utcoffset()
    if offset is None:
        return "UTC"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def convert(moment: dt.datetime, target_zone: str) -> dt.datetime:
    if moment.tzinfo is None:
        moment = moment.astimezone()
    return moment.astimezone(resolve_zone(target_zone))


def parse_datetime(text: str, default_zone: str | None = None) -> dt.datetime:
    cleaned = (text or "").strip()
    if not cleaned:
        raise TimeZoneError("Enter a date and time")
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%m/%d/%Y %H:%M",
        "%H:%M:%S",
        "%H:%M",
    )
    base_date = dt.datetime.now(resolve_zone(default_zone)) if default_zone else dt.datetime.now()
    for pattern in formats:
        try:
            parsed = dt.datetime.strptime(cleaned, pattern)
        except ValueError:
            continue
        if pattern in ("%H:%M", "%H:%M:%S"):
            parsed = parsed.replace(year=base_date.year, month=base_date.month, day=base_date.day)
        if parsed.tzinfo is None:
            tzinfo = base_date.tzinfo
            parsed = parsed.replace(tzinfo=tzinfo) if tzinfo else parsed.astimezone()
        return parsed
    try:
        parsed = dt.datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed
    except ValueError as exc:
        raise TimeZoneError("Unrecognised date/time format") from exc


def date_difference(first: dt.datetime, second: dt.datetime) -> dt.timedelta:
    return second - first


def describe_delta(delta: dt.timedelta) -> str:
    total_seconds = int(delta.total_seconds())
    sign = "ago" if total_seconds < 0 else "from now"
    total_seconds = abs(total_seconds)
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds and not days:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return f"{', '.join(parts) or '0 seconds'} {sign}"


def time_in_zone(zone_name: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> dict[str, str]:
    moment = now(zone_name)
    return {
        "zone": zone_name,
        "time": moment.strftime(fmt),
        "offset": utc_offset(moment),
        "weekday": moment.strftime("%A"),
        "iso": moment.isoformat(timespec="seconds"),
    }


def parse_time_query(text: str) -> dict[str, Any] | None:
    """Parse ``"Tokyo"``, ``"14:30 to Tokyo"`` or ``"14:30 UTC to Tokyo"``."""
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    conversion = re.match(r"^(.*?)\s+(?:to|in|->|→)\s+(.+)$", cleaned, re.IGNORECASE)
    if conversion:
        left, right = conversion.group(1).strip(), conversion.group(2).strip()
        target = find_zone(right)
        if target is None:
            return None
        source_zone = None
        time_match = re.match(r"^(\d{1,2}:\d{2}(?::\d{2})?)\s*(.*)$", left)
        if time_match:
            time_text = time_match.group(1)
            remainder = time_match.group(2).strip()
            if remainder:
                source_zone = find_zone(remainder)
                if source_zone is None:
                    return None
            try:
                moment = parse_datetime(time_text, default_zone=source_zone)
            except TimeZoneError:
                return None
            return {"kind": "convert", "moment": moment, "target": target}
        return {"kind": "zone", "target": target, "source": left}
    zone = find_zone(cleaned)
    if zone is not None:
        return {"kind": "zone", "target": zone}
    return None


class DateTimeProvider(SearchProvider):
    """The ``time`` keyword."""

    id = "datetime"
    title = "Date and time"
    keyword = "time"
    weight = 1.0
    auto = False

    def _fmt(self) -> str:
        return str(self.config.get("date_time.format", "%Y-%m-%d %H:%M:%S") or "%Y-%m-%d %H:%M:%S")

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip()
        if not text:
            return self.suggestions(limit)
        parsed = parse_time_query(text)
        if parsed is None:
            return [
                self.make_result(
                    title=f"Unknown time zone: {text}",
                    subtitle="Try a city or IANA name, e.g. Tokyo or Europe/Istanbul",
                    category="Date & Time",
                    score=0.8,
                    primary=lambda: self.hooks.open_tools("datetime"),
                    icon_glyph="◷",
                )
            ]
        if parsed["kind"] == "convert":
            target = parsed["target"]
            converted = convert(parsed["moment"], target)
            source_label = str(parsed["moment"].tzinfo)
            value = converted.strftime(self._fmt())
            return [
                self.make_result(
                    title=f"{value}  ·  {target}",
                    subtitle=f"{source_label} → {target}  ·  {utc_offset(converted)}",
                    category="Date & Time",
                    score=0.95,
                    primary=lambda: self.hooks.copy_text(value),
                    actions=[ResultAction("Copy with time zone", lambda: self.hooks.copy_text(f"{value} {target}"))],
                    copy_text=value,
                    icon_glyph="◷",
                )
            ]
        zone = parsed["target"]
        try:
            info = time_in_zone(zone, self._fmt())
        except TimeZoneError as exc:
            return [
                self.make_result(
                    title="Time zone unavailable",
                    subtitle=str(exc),
                    category="Date & Time",
                    score=0.8,
                    icon_glyph="◷",
                )
            ]
        return [
            self.make_result(
                title=f"{info['time']}  ·  {zone}",
                subtitle=f"{info['weekday']}  ·  {info['offset']}",
                category="Date & Time",
                score=0.95,
                primary=lambda: self.hooks.copy_text(f"{info['time']} {zone}"),
                actions=[
                    ResultAction("Open date & time tools", lambda: self.hooks.open_tools("datetime")),
                    ResultAction(
                        "Copy ISO timestamp",
                        lambda: self.hooks.copy_text(info["iso"]),
                    ),
                ],
                copy_text=info["time"],
                icon_glyph="◷",
            )
        ]

    def suggestions(self, limit: int) -> list[SearchResult]:
        results: list[SearchResult] = []
        local = now()
        fmt = self._fmt()
        results.append(
            self.make_result(
                title=local.strftime(fmt),
                subtitle=f"Local time  ·  {local.strftime('%A')}  ·  {utc_offset(local)}",
                category="Date & Time",
                score=0.8,
                primary=lambda: self.hooks.copy_text(local.strftime(fmt)),
                actions=[ResultAction("Open date & time tools", lambda: self.hooks.open_tools("datetime"))],
                copy_text=local.strftime(fmt),
                icon_glyph="◷",
            )
        )
        favourites = self.config.get("date_time.favourite_zones", []) or []
        for zone in favourites[: max(0, min(limit - 1, 3))]:
            try:
                info = time_in_zone(str(zone), fmt)
            except TimeZoneError:
                continue
            results.append(
                self.make_result(
                    title=f"{info['time']}  ·  {zone}",
                    subtitle=f"{info['weekday']}  ·  {info['offset']}",
                    category="Date & Time",
                    score=0.7,
                    primary=lambda z=str(zone): self.hooks.copy_text(time_in_zone(z, self._fmt())["time"]),
                    copy_text=info["time"],
                    icon_glyph="◷",
                )
            )
        return results

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Date and time",
            subtitle="Try: time: Tokyo  ·  time: 14:30 to UTC",
            category="Date & Time",
            score=1.0,
            primary=lambda: self.hooks.fill_query("time: Tokyo"),
            icon_glyph="◷",
        )


__all__ = [
    "TimeZoneError",
    "resolve_zone",
    "find_zone",
    "zone_names",
    "now",
    "format_datetime",
    "utc_offset",
    "convert",
    "parse_datetime",
    "date_difference",
    "describe_delta",
    "time_in_zone",
    "parse_time_query",
    "DateTimeProvider",
]
