from __future__ import annotations

from features.file_query import parse_file_query


def test_parse_extension_and_modified_period():
    parsed = parse_file_query("invoices type:pdf modified last week", now=1_000_000)
    assert parsed.text == "invoices"
    assert parsed.extension == ".pdf"
    assert parsed.modified_after == 1_000_000 - 7 * 86400


def test_parse_size_filter_and_preserve_unknown_words():
    parsed = parse_file_query("large video larger than 500 MB", now=100)
    assert parsed.text == "large video"
    assert parsed.size_operator == ">"
    assert parsed.size_bytes == 500_000_000


def test_parse_smaller_than_and_yesterday():
    from datetime import datetime, timedelta

    now = 200_000
    local_now = datetime.fromtimestamp(now)
    today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    parsed = parse_file_query("smaller than 2 KiB modified yesterday", now=now)
    assert parsed.text == ""
    assert parsed.size_operator == "<"
    assert parsed.size_bytes == 2048
    assert parsed.modified_after == (today_start - timedelta(days=1)).timestamp()
    assert parsed.modified_before == today_start.timestamp()


def test_unrecognised_query_is_unchanged():
    parsed = parse_file_query("quarterly invoices")
    assert parsed.text == "quarterly invoices"
    assert not parsed.extension
    assert parsed.modified_after is None
    assert parsed.size_bytes is None



def test_modified_yesterday_uses_local_calendar_boundaries():
    from datetime import datetime

    now = datetime(2026, 11, 19, 12, 0, 0).timestamp()
    parsed = parse_file_query("invoices modified yesterday", now=now)
    today_start = datetime(2026, 11, 19, 0, 0, 0).timestamp()
    yesterday_start = datetime(2026, 11, 18, 0, 0, 0).timestamp()
    assert parsed.modified_after == yesterday_start
    assert parsed.modified_before == today_start


def test_modified_today_starts_at_local_midnight():
    from datetime import datetime

    now = datetime(2026, 11, 19, 12, 0, 0).timestamp()
    parsed = parse_file_query("modified today", now=now)
    assert parsed.modified_after == datetime(2026, 11, 19, 0, 0, 0).timestamp()
    assert parsed.modified_before is None


def test_parse_size_range_with_decimal_and_binary_units():
    parsed = parse_file_query("archive larger than 500 MB smaller than 2 GiB")
    assert parsed.text == "archive"
    assert parsed.size_min_bytes == 500_000_000
    assert parsed.size_max_bytes == 2 * 1024**3
