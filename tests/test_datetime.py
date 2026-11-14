from __future__ import annotations

import datetime as dt

import pytest

from features import date_time
from features.date_time import DateTimeProvider, TimeZoneError


def test_zone_resolution():
    assert str(date_time.resolve_zone("UTC")) == "UTC"
    assert "Istanbul" in str(date_time.resolve_zone("Istanbul"))
    assert "Tokyo" in str(date_time.resolve_zone("Asia/Tokyo"))
    with pytest.raises(TimeZoneError):
        date_time.resolve_zone("Not/AZone")
    assert date_time.find_zone("tokyo")


def test_time_in_zone():
    info = date_time.time_in_zone("Europe/Istanbul")
    assert info["zone"] == "Europe/Istanbul"
    assert info["offset"].startswith("UTC")
    assert info["weekday"]


def test_parse_and_convert():
    parsed = date_time.parse_datetime("2026-01-31 14:30", default_zone="UTC")
    assert parsed.year == 2026 and parsed.hour == 14
    converted = date_time.convert(parsed, "Asia/Tokyo")
    assert converted.hour == 23
    short = date_time.parse_datetime("14:30", default_zone="UTC")
    assert short.hour == 14
    with pytest.raises(TimeZoneError):
        date_time.parse_datetime("not a date")


def test_date_difference():
    first = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    second = dt.datetime(2026, 1, 3, 6, tzinfo=dt.timezone.utc)
    delta = date_time.date_difference(first, second)
    assert delta.days == 2 and delta.seconds == 6 * 3600
    assert "2 days" in date_time.describe_delta(delta)


def test_parse_time_query():
    assert date_time.parse_time_query("Tokyo")["kind"] == "zone"
    query = date_time.parse_time_query("14:30 to Tokyo")
    assert query["kind"] == "convert" and "Tokyo" in query["target"]
    assert date_time.parse_time_query("14:30 UTC to Tokyo")["kind"] == "convert"
    assert date_time.parse_time_query("asdkjhqwe") is None


def test_provider_zone_lookup(config, db, hooks):
    provider = DateTimeProvider(config, db, hooks)
    results = provider.search("Tokyo", 5)
    assert results and "Asia/Tokyo" in results[0].title
    results[0].execute()
    assert any(call[0] == "copy_text" for call in hooks.calls)


def test_provider_conversion(config, db, hooks):
    provider = DateTimeProvider(config, db, hooks)
    results = provider.search("14:30 to UTC", 5)
    assert results and "UTC" in results[0].title
    assert provider.search("Not/AZone", 5)[0].title.startswith("Unknown time zone")


def test_provider_suggestions(config, db, hooks):
    provider = DateTimeProvider(config, db, hooks)
    results = provider.suggestions(4)
    assert results
    assert "Local time" in results[0].subtitle
