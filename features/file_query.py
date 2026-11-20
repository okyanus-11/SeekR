"""Small, predictable natural-language grammar for indexed file searches.

Supported examples: "invoices modified last week", "report type:pdf",
"large video files larger than 500 MB". Unrecognised words stay in the
filename query so ordinary search remains unchanged.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta
from dataclasses import dataclass

_EXTENSION = re.compile(r"\b(?:ext|type):([a-z0-9]+)\b", re.IGNORECASE)
_MODIFIED = re.compile(r"\bmodified\s+(today|yesterday|last\s+week|last\s+month)\b", re.IGNORECASE)
_SIZE = re.compile(
    r"\b(larger|bigger|smaller)\s+than\s+(\d+(?:\.\d+)?)\s*(bytes?|kb|kib|mb|mib|gb|gib)\b",
    re.IGNORECASE,
)
_MULTIPLIERS = {
    "byte": 1, "bytes": 1, "kb": 1000, "kib": 1024,
    "mb": 1000**2, "mib": 1024**2, "gb": 1000**3, "gib": 1024**3,
}


@dataclass(frozen=True)
class FileQuery:
    text: str
    extension: str = ""
    modified_after: float | None = None
    modified_before: float | None = None
    size_operator: str | None = None
    size_bytes: int | None = None
    size_min_bytes: int | None = None
    size_max_bytes: int | None = None


def parse_file_query(query: str, now: float | None = None) -> FileQuery:
    text = (query or "").strip()
    extension = ""
    modified_after = None
    modified_before = None
    size_operator = None
    size_bytes = None
    size_min_bytes = None
    size_max_bytes = None
    match = _EXTENSION.search(text)
    if match:
        extension = "." + match.group(1).lower().lstrip(".")
        text = _EXTENSION.sub("", text).strip()
    match = _MODIFIED.search(text)
    if match:
        period = re.sub(r"\s+", " ", match.group(1).lower())
        current = time.time() if now is None else float(now)
        if period in {"today", "yesterday"}:
            local_now = datetime.fromtimestamp(current)
            today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
            if period == "today":
                modified_after = today_start.timestamp()
            else:
                modified_after = (today_start - timedelta(days=1)).timestamp()
                modified_before = today_start.timestamp()
        else:
            days = {"last week": 7, "last month": 30}[period]
            modified_after = current - days * 86400
        text = _MODIFIED.sub("", text).strip()
    matches = list(_SIZE.finditer(text))
    for match in matches:
        operator = "<" if match.group(1).lower() == "smaller" else ">"
        amount = int(float(match.group(2)) * _MULTIPLIERS[match.group(3).lower()])
        if operator == "<":
            size_max_bytes = amount if size_max_bytes is None else min(size_max_bytes, amount)
        else:
            size_min_bytes = amount if size_min_bytes is None else max(size_min_bytes, amount)
        if size_operator is None:
            size_operator, size_bytes = operator, amount
    if matches:
        text = _SIZE.sub("", text).strip()
    return FileQuery(text=text, extension=extension, modified_after=modified_after,
                     modified_before=modified_before, size_operator=size_operator,
                     size_bytes=size_bytes, size_min_bytes=size_min_bytes,
                     size_max_bytes=size_max_bytes)
