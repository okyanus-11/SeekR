from __future__ import annotations

import pytest

from features.calculator import (
    CalculatorError,
    CalculatorService,
    convert_units,
    evaluate,
    format_number,
    looks_like_conversion,
    looks_like_math,
    normalise_expression,
)


def test_basic_arithmetic():
    assert evaluate("2+2") == "4"
    assert evaluate("25 * 48") == "1200"
    assert evaluate("(12 + 8) / 4") == "5"
    assert evaluate("2^10") == "1024"
    assert evaluate("10 - 3 * 2") == "4"


def test_required_example():
    assert evaluate("sqrt(144) + 25 * 4") == "112"


def test_constants_and_functions():
    assert evaluate("pi").startswith("3.14159265")
    assert evaluate("sin(pi/2)") == "1"
    assert evaluate("log(1000)") == "3"
    assert evaluate("ln(e)") == "1"
    assert evaluate("abs(-7)") == "7"
    assert evaluate("factorial(5)") == "120"


def test_precision_is_configurable():
    assert evaluate("1/3", precision=4) == "0.3333"
    assert evaluate("1/3", precision=12) == "0.333333333333"
    assert format_number(10, 3) == "10"


def test_percentages():
    assert evaluate("15% of 80") == "12"
    assert evaluate("50 + 20%") == "60"
    assert evaluate("20%") == "0.2"


def test_angle_units():
    assert evaluate("sin(90)", angle_unit="deg") == "1"
    assert evaluate("cos(0)", angle_unit="deg") == "1"


def test_normalisation():
    assert normalise_expression("2 × 3") == "2 * 3"
    assert normalise_expression("10 ÷ 2") == "10 / 2"
    assert normalise_expression("2^3") == "2**3"
    assert normalise_expression("1,000 + 1") == "1000 + 1"


def test_invalid_expressions_raise():
    for expression in ("", "hello", "2 +", "sqrt(", "1/0", "2 %% 4"):
        with pytest.raises(CalculatorError):
            evaluate(expression)


def test_unsafe_input_is_rejected():
    with pytest.raises(CalculatorError):
        evaluate("__import__('os').system('echo hacked')")
    with pytest.raises(CalculatorError):
        evaluate("open('/etc/passwd')")
    with pytest.raises(CalculatorError):
        evaluate("().__class__")
    with pytest.raises(CalculatorError):
        evaluate("lambda: 1")


def test_looks_like_math():
    assert looks_like_math("25 * 48")
    assert looks_like_math("sqrt(144) + 25 * 4")
    assert looks_like_math("2e5")
    assert not looks_like_math("discord")
    assert not looks_like_math("raspberry pi 5")
    assert not looks_like_math("ipconfig")
    assert not looks_like_math("")


def test_unit_conversion():
    assert convert_units("100 km to miles").startswith("62.137")
    assert convert_units("100 km to miles").endswith("mi")
    assert convert_units("1 gb to mb") == "1000 mb"
    assert convert_units("72 f to c").startswith("22.22")
    assert convert_units("2 h to min") == "120 min"
    assert looks_like_conversion("100 km to miles")
    assert not looks_like_conversion("2 + 2")


def test_invalid_conversions():
    with pytest.raises(CalculatorError):
        convert_units("100 km to bananas")
    with pytest.raises(CalculatorError):
        convert_units("100 km to kg")
    with pytest.raises(CalculatorError):
        convert_units("not a conversion")


def test_service_and_history(config, db):
    service = CalculatorService(config, db)
    outcome = service.evaluate_text("2 + 2")
    assert outcome.ok and outcome.result == "4"
    service.record(outcome)
    assert service.history()
    assert "2 + 2 = 4" in service.history()[0]
    failed = service.evaluate_text("2 +")
    assert not failed.ok and failed.error
    service.clear_history()
    assert service.history() == []


def test_provider_returns_result_and_copies(config, db, hooks):
    from features.calculator import CalculatorProvider

    provider = CalculatorProvider(config, db, hooks, CalculatorService(config, db))
    results = provider.search("sqrt(144) + 25 * 4", 5)
    assert results and results[0].title == "112"
    results[0].execute()
    assert ("copy_text", ("112",)) in hooks.calls
    assert provider.search("not math at all", 5) == []
    assert provider.search("", 5) == []
