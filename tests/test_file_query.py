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
    parsed = parse_file_query("smaller than 2 KiB modified yesterday", now=200_000)
    assert parsed.text == ""
    assert parsed.size_operator == "<"
    assert parsed.size_bytes == 2048
    assert parsed.modified_after == 200_000 - 2 * 86400


def test_unrecognised_query_is_unchanged():
    parsed = parse_file_query("quarterly invoices")
    assert parsed.text == "quarterly invoices"
    assert not parsed.extension
    assert parsed.modified_after is None
    assert parsed.size_bytes is None
