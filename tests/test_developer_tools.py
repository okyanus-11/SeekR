from __future__ import annotations

import pytest

from features import developer_tools as tools


def test_uuid_generation():
    value = tools.generate_uuid(4)
    assert len(value) == 36 and value.count("-") == 4
    assert value != tools.generate_uuid(4)
    assert tools.generate_uuid(1).count("-") == 4
    with pytest.raises(tools.ToolError):
        tools.generate_uuid(7)


def test_base64_roundtrip():
    encoded = tools.base64_encode("SeekR ✓")
    assert tools.base64_decode(encoded) == "SeekR ✓"
    assert tools.base64_encode("abc", url_safe=True)
    with pytest.raises(tools.ToolError):
        tools.base64_decode("!!not-base64!!")


def test_json_tools():
    formatted = tools.json_format('{"a":1,"b":[2,3]}')
    assert '"a": 1' in formatted
    assert tools.json_minify('{ "a" : 1 }') == '{"a":1}'
    ok, message = tools.json_validate('{"ok":true}')
    assert ok and "Valid" in message
    ok, message = tools.json_validate("{bad}")
    assert not ok and "line 1" in message
    with pytest.raises(tools.ToolError):
        tools.json_format("{bad}")


def test_url_tools():
    encoded = tools.url_encode("a b&c=d")
    assert encoded == "a%20b%26c%3Dd"
    assert tools.url_decode(encoded) == "a b&c=d"
    parsed = tools.url_parse("https://example.com/path?q=1#frag")
    assert parsed["host"] == "example.com" and parsed["fragment"] == "frag"


def test_hash_tools():
    assert tools.hash_text("abc", "md5") == "900150983cd24fb0d6963f7d28e17f72"
    assert len(tools.hash_text("abc", "sha256")) == 64
    with pytest.raises(tools.ToolError):
        tools.hash_text("abc", "nope")


def test_color_tools():
    assert tools.parse_color("#f80") == (255, 136, 0)
    assert tools.parse_color("#ff8800") == (255, 136, 0)
    assert tools.parse_color("rgb(255, 136, 0)") == (255, 136, 0)
    formats = tools.color_formats("#ff8800")
    assert formats["hex"] == "#ff8800"
    assert formats["rgb"] == "rgb(255, 136, 0)"
    assert formats["decimal"] == str(0xFF8800)
    assert formats["hsl"].startswith("hsl(")
    with pytest.raises(tools.ToolError):
        tools.parse_color("octarine")
    with pytest.raises(tools.ToolError):
        tools.parse_color("rgb(300, 0, 0)")


def test_regex_tester():
    result = tools.test_regex(r"\b[A-Z]\w+", "Hello World from SeekR")
    assert result["count"] == 3
    assert result["matches"][0]["match"] == "Hello"
    flags = tools.test_regex("hello", "HELLO", "i")
    assert flags["count"] == 1
    with pytest.raises(tools.ToolError):
        tools.test_regex("(", "text")


def test_timestamp_tools():
    stamp = tools.datetime_to_timestamp("2026-01-31 14:30:00")
    assert isinstance(stamp, float) and stamp > 0
    text = tools.timestamp_to_datetime(stamp)
    assert "2026-01-31" in text
    assert tools.datetime_to_timestamp(str(int(stamp * 1000))) == pytest.approx(stamp, abs=1)
    with pytest.raises(tools.ToolError):
        tools.datetime_to_timestamp("not a date")
    info = tools.now_info()
    assert int(info["epoch"]) > 0


def test_case_conversion():
    assert tools.to_snake_case("Hello World Example") == "hello_world_example"
    assert tools.to_kebab_case("Hello World") == "hello-world"
    assert tools.to_camel_case("hello world example") == "helloWorldExample"
    assert tools.to_pascal_case("hello world") == "HelloWorld"
    assert tools.to_constant_case("hello world") == "HELLO_WORLD"
    assert tools.change_case("hello", "upper") == "HELLO"
    with pytest.raises(tools.ToolError):
        tools.change_case("hello", "klingon")


def test_counts():
    counts = tools.count_text("Hello world.\n\nSecond line here!")
    assert counts["characters"] > 0
    assert counts["words"] == 5
    assert counts["lines"] == 3
    assert counts["paragraphs"] == 2
    assert counts["sentences"] == 2


def test_hex_and_binary():
    encoded = tools.text_to_hex("SeekR")
    assert tools.hex_to_text(encoded) == "SeekR"
    assert tools.binary_to_text(tools.text_to_binary("SeekR")) == "SeekR"
    with pytest.raises(tools.ToolError):
        tools.hex_to_text("zz")
    with pytest.raises(tools.ToolError):
        tools.binary_to_text("101")
