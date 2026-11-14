"""Developer utilities implemented as pure, testable functions."""

from __future__ import annotations

import base64
import binascii
import colorsys
import datetime as dt
import hashlib
import json
import re
import time
import urllib.parse
import uuid
from typing import Any

HASH_ALGORITHMS = ("md5", "sha1", "sha224", "sha256", "sha384", "sha512", "blake2b", "blake2s")


class ToolError(ValueError):
    """Raised when a developer tool receives invalid input."""


# --------------------------------------------------------------------- UUID
def generate_uuid(version: int = 4) -> str:
    if version == 1:
        return str(uuid.uuid1())
    if version == 4:
        return str(uuid.uuid4())
    raise ToolError("Only UUID v1 and v4 are supported")


# ------------------------------------------------------------------- Base64
def base64_encode(text: str, url_safe: bool = False) -> str:
    data = text.encode("utf-8")
    encoded = base64.urlsafe_b64encode(data) if url_safe else base64.b64encode(data)
    return encoded.decode("ascii")


def base64_decode(text: str) -> str:
    cleaned = "".join(text.split())
    if not cleaned:
        raise ToolError("Nothing to decode")
    padding = "=" * (-len(cleaned) % 4)
    try:
        data = base64.urlsafe_b64decode(cleaned + padding)
    except (binascii.Error, ValueError) as exc:
        raise ToolError("The input is not valid Base64") from exc
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ToolError("The decoded bytes are not valid UTF-8 text") from exc


# --------------------------------------------------------------------- JSON
def json_format(text: str, indent: int = 2, sort_keys: bool = False) -> str:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolError(f"Invalid JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    return json.dumps(parsed, indent=indent, ensure_ascii=False, sort_keys=sort_keys)


def json_minify(text: str) -> str:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolError(f"Invalid JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc
    return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)


def json_validate(text: str) -> tuple[bool, str]:
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"Invalid JSON: line {exc.lineno}, column {exc.colno}: {exc.msg}"
    return True, "Valid JSON"


# ----------------------------------------------------------------------- URL
def url_encode(text: str) -> str:
    return urllib.parse.quote(text, safe="")


def url_decode(text: str) -> str:
    try:
        return urllib.parse.unquote(text, errors="strict")
    except UnicodeDecodeError as exc:
        raise ToolError("The input is not valid percent-encoded UTF-8") from exc


def url_parse(text: str) -> dict[str, str]:
    parsed = urllib.parse.urlparse(text)
    return {
        "scheme": parsed.scheme,
        "host": parsed.netloc,
        "path": parsed.path,
        "query": parsed.query,
        "fragment": parsed.fragment,
    }


# --------------------------------------------------------------------- hashes
def hash_text(text: str, algorithm: str = "sha256") -> str:
    algorithm = algorithm.lower()
    if algorithm not in HASH_ALGORITHMS:
        raise ToolError(f"Unsupported hash algorithm: {algorithm}")
    try:
        return hashlib.new(algorithm, text.encode("utf-8")).hexdigest()
    except ValueError as exc:
        raise ToolError(f"Hash algorithm unavailable: {algorithm}") from exc


# --------------------------------------------------------------------- colors
def parse_color(value: str) -> tuple[int, int, int]:
    text = (value or "").strip().lower()
    if not text:
        raise ToolError("Enter a color")
    match = re.fullmatch(r"#?([0-9a-f]{3})", text)
    if match:
        digits = match.group(1)
        return tuple(int(ch * 2, 16) for ch in digits)  # type: ignore[return-value]
    match = re.fullmatch(r"#?([0-9a-f]{6})", text)
    if match:
        digits = match.group(1)
        return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
    match = re.fullmatch(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*[\d.]+\s*)?\)", text)
    if match:
        values = tuple(int(match.group(i)) for i in (1, 2, 3))
        if any(component > 255 for component in values):
            raise ToolError("RGB components must be between 0 and 255")
        return values  # type: ignore[return-value]
    match = re.fullmatch(r"hsl\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*\)", text)
    if match:
        hue = float(match.group(1)) % 360
        saturation = float(match.group(2)) / 100
        lightness = float(match.group(3)) / 100
        r, g, b = colorsys.hls_to_rgb(hue / 360, lightness, saturation)
        return (round(r * 255), round(g * 255), round(b * 255))
    raise ToolError("Use #RGB, #RRGGBB, rgb(r,g,b) or hsl(h,s%,l%)")


def to_hex(value: str | tuple[int, int, int]) -> str:
    rgb = parse_color(value) if isinstance(value, str) else value
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def to_rgb(value: str | tuple[int, int, int]) -> tuple[int, int, int]:
    return parse_color(value) if isinstance(value, str) else value


def to_hsl(value: str | tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = to_rgb(value)
    hue, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return (hue * 360, saturation * 100, lightness * 100)


def to_hsv(value: str | tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = to_rgb(value)
    hue, saturation, brightness = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return (hue * 360, saturation * 100, brightness * 100)


def color_formats(value: str) -> dict[str, str]:
    rgb = parse_color(value)
    hue, saturation, lightness = to_hsl(rgb)
    hue_v, saturation_v, brightness_v = to_hsv(rgb)
    return {
        "hex": to_hex(rgb),
        "rgb": "rgb({}, {}, {})".format(*rgb),
        "hsl": f"hsl({hue:.0f}, {saturation:.0f}%, {lightness:.0f}%)",
        "hsv": f"hsv({hue_v:.0f}, {saturation_v:.0f}%, {brightness_v:.0f}%)",
        "decimal": str((rgb[0] << 16) + (rgb[1] << 8) + rgb[2]),
    }


# ---------------------------------------------------------------------- regex
def test_regex(pattern: str, text: str, flags: str = "", max_matches: int = 200) -> dict[str, Any]:
    if not pattern:
        raise ToolError("Enter a regular expression")
    flag_value = 0
    if "i" in flags:
        flag_value |= re.IGNORECASE
    if "m" in flags:
        flag_value |= re.MULTILINE
    if "s" in flags:
        flag_value |= re.DOTALL
    if "x" in flags:
        flag_value |= re.VERBOSE
    try:
        compiled = re.compile(pattern, flag_value)
    except re.error as exc:
        raise ToolError(f"Invalid regular expression: {exc}") from exc
    matches = []
    for index, match in enumerate(compiled.finditer(text)):
        if index >= max_matches:
            break
        matches.append(
            {
                "match": match.group(0),
                "start": match.start(),
                "end": match.end(),
                "groups": list(match.groups()),
                "named": match.groupdict(),
            }
        )
    return {
        "count": len(matches),
        "matches": matches,
        "truncated": len(matches) >= max_matches,
    }


# ------------------------------------------------------------------ timestamps
def timestamp_to_datetime(value: float, timezone_offset_hours: float | None = None) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ToolError("The timestamp must be a number") from exc
    if abs(numeric) > 1e11:  # milliseconds
        numeric /= 1000.0
    if timezone_offset_hours is None:
        moment = dt.datetime.fromtimestamp(numeric)
        suffix = "local"
    else:
        moment = dt.datetime.fromtimestamp(numeric, dt.timezone(dt.timedelta(hours=timezone_offset_hours)))
        suffix = f"UTC{timezone_offset_hours:+g}"
    return f"{moment.strftime('%Y-%m-%d %H:%M:%S')} ({suffix})"


def datetime_to_timestamp(text: str) -> float:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ToolError("Enter a date or timestamp")
    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d.%m.%Y %H:%M",
        "%d.%m.%Y",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    )
    if re.fullmatch(r"\d{9,13}", cleaned):
        value = float(cleaned)
        return value / 1000 if value > 1e11 else value
    iso_candidate = cleaned.replace("Z", "+00:00")
    try:
        parsed = dt.datetime.fromisoformat(iso_candidate)
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed.timestamp()
    except ValueError:
        pass
    for pattern in formats:
        try:
            return dt.datetime.strptime(cleaned, pattern).timestamp()
        except ValueError:
            continue
    raise ToolError("Unrecognised date format (try 2026-01-31 14:30 or an epoch timestamp)")


def now_info() -> dict[str, str]:
    moment = dt.datetime.now()
    return {
        "local": moment.strftime("%Y-%m-%d %H:%M:%S"),
        "iso": moment.isoformat(timespec="seconds"),
        "utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": str(int(time.time())),
        "epoch_ms": str(int(time.time() * 1000)),
        "weekday": moment.strftime("%A"),
        "week": str(moment.isocalendar().week),
        "timezone": time.strftime("%Z"),
    }


# ------------------------------------------------------------------ text tools
def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÿ0-9']+", text)


def to_snake_case(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    return "_".join(word.lower() for word in words)


def to_kebab_case(text: str) -> str:
    return to_snake_case(text).replace("_", "-")


def to_camel_case(text: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text)
    if not words:
        return ""
    first, *rest = words
    return first.lower() + "".join(word.capitalize() for word in rest)


def to_pascal_case(text: str) -> str:
    return "".join(word.capitalize() for word in re.findall(r"[A-Za-z0-9]+", text))


def to_constant_case(text: str) -> str:
    return to_snake_case(text).upper()


def to_title_case(text: str) -> str:
    return " ".join(word.capitalize() for word in re.findall(r"[A-Za-z0-9']+", text))


def change_case(text: str, mode: str) -> str:
    mode = mode.lower()
    options = {
        "upper": str.upper,
        "lower": str.lower,
        "title": to_title_case,
        "snake": to_snake_case,
        "kebab": to_kebab_case,
        "camel": to_camel_case,
        "pascal": to_pascal_case,
        "constant": to_constant_case,
        "sentence": lambda value: (value.strip()[:1].upper() + value.strip()[1:].lower()) if value.strip() else "",
    }
    if mode not in options:
        raise ToolError(f"Unknown case: {mode}")
    return options[mode](text)


def count_text(text: str) -> dict[str, int]:
    lines = text.splitlines()
    sentences = [part for part in re.split(r"[.!?]+(?:\s|$)", text) if part.strip()]
    paragraphs = [block for block in re.split(r"\n\s*\n", text) if block.strip()]
    return {
        "characters": len(text),
        "characters_no_spaces": len(re.sub(r"\s", "", text)),
        "words": len(_words(text)),
        "lines": len(lines),
        "sentences": len(sentences),
        "paragraphs": len(paragraphs),
    }


def text_to_hex(text: str) -> str:
    return text.encode("utf-8").hex(" ")


def hex_to_text(text: str) -> str:
    cleaned = re.sub(r"[\s,0x]+", " ", text.lower()).strip()
    if not cleaned:
        raise ToolError("Nothing to decode")
    try:
        return bytes.fromhex(cleaned.replace(" ", "")).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ToolError("The input is not valid hexadecimal UTF-8 text") from exc


def text_to_binary(text: str) -> str:
    return " ".join(format(byte, "08b") for byte in text.encode("utf-8"))


def binary_to_text(text: str) -> str:
    cleaned = re.sub(r"[^01]", "", text)
    if not cleaned or len(cleaned) % 8:
        raise ToolError("Binary input must contain whole bytes")
    try:
        return bytes(int(cleaned[i : i + 8], 2) for i in range(0, len(cleaned), 8)).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ToolError("The binary data is not valid UTF-8 text") from exc


__all__ = [
    "HASH_ALGORITHMS",
    "ToolError",
    "generate_uuid",
    "base64_encode",
    "base64_decode",
    "json_format",
    "json_minify",
    "json_validate",
    "url_encode",
    "url_decode",
    "url_parse",
    "hash_text",
    "parse_color",
    "to_hex",
    "to_rgb",
    "to_hsl",
    "to_hsv",
    "color_formats",
    "test_regex",
    "timestamp_to_datetime",
    "datetime_to_timestamp",
    "now_info",
    "to_snake_case",
    "to_kebab_case",
    "to_camel_case",
    "to_pascal_case",
    "to_constant_case",
    "to_title_case",
    "change_case",
    "count_text",
    "text_to_hex",
    "hex_to_text",
    "text_to_binary",
    "binary_to_text",
]
