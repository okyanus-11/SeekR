"""Calculator and unit conversion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from core.config_manager import ConfigManager
from core.database import Database
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

log = get_logger(__name__)


class CalculatorError(ValueError):
    """Raised for invalid or unsafe expressions."""


_MATH_WORDS = {
    "sqrt", "cbrt", "root", "sin", "cos", "tan", "asin", "acos", "atan",
    "sinh", "cosh", "tanh", "log", "ln", "lg", "log2", "log10", "exp",
    "abs", "factorial", "floor", "ceil", "ceiling", "round", "sign", "mod",
    "pi", "e", "tau", "phi", "inf", "nan", "deg", "rad",
}

_CONVERSION_RE = re.compile(
    r"^\s*(-?\d+(?:[.,]\d+)?)\s*([A-Za-z°µ²³/ ]+?)\s+(?:to|in|->|→)\s+([A-Za-z°µ²³/ ]+?)\s*$",
    re.IGNORECASE,
)

# unit -> (dimension, factor to the dimension's base unit)
_UNIT_TABLE: dict[str, tuple[str, float]] = {
    # length (metre)
    "m": ("length", 1.0), "meter": ("length", 1.0), "metre": ("length", 1.0),
    "km": ("length", 1000.0), "kilometer": ("length", 1000.0), "kilometre": ("length", 1000.0),
    "cm": ("length", 0.01), "mm": ("length", 0.001), "µm": ("length", 1e-6), "um": ("length", 1e-6),
    "nm": ("length", 1e-9), "mi": ("length", 1609.344), "mile": ("length", 1609.344),
    "ft": ("length", 0.3048), "foot": ("length", 0.3048), "feet": ("length", 0.3048),
    "in": ("length", 0.0254), "inch": ("length", 0.0254),
    "yd": ("length", 0.9144), "yard": ("length", 0.9144),
    "nmi": ("length", 1852.0), "lightyear": ("length", 9.4607e15),
    # mass (kilogram)
    "kg": ("mass", 1.0), "kilogram": ("mass", 1.0), "g": ("mass", 0.001),
    "gram": ("mass", 0.001), "mg": ("mass", 1e-6), "µg": ("mass", 1e-9),
    "lb": ("mass", 0.45359237), "lbs": ("mass", 0.45359237), "pound": ("mass", 0.45359237),
    "oz": ("mass", 0.028349523125), "ounce": ("mass", 0.028349523125),
    "stone": ("mass", 6.35029318), "ton": ("mass", 907.18474), "tonne": ("mass", 1000.0),
    # volume (litre)
    "l": ("volume", 1.0), "liter": ("volume", 1.0), "litre": ("volume", 1.0),
    "ml": ("volume", 0.001), "m3": ("volume", 1000.0), "cm3": ("volume", 0.001),
    "gal": ("volume", 3.785411784), "gallon": ("volume", 3.785411784),
    "qt": ("volume", 0.946352946), "quart": ("volume", 0.946352946),
    "pt": ("volume", 0.473176473), "pint": ("volume", 0.473176473),
    "cup": ("volume", 0.2365882365), "floz": ("volume", 0.0295735295625),
    "tbsp": ("volume", 0.01478676478125), "tsp": ("volume", 0.00492892159375),
    # speed (m/s)
    "m/s": ("speed", 1.0), "km/h": ("speed", 0.2777777778), "kph": ("speed", 0.2777777778),
    "mph": ("speed", 0.44704), "knot": ("speed", 0.5144444444), "ft/s": ("speed", 0.3048),
    # data (byte)
    "b": ("data", 1.0), "byte": ("data", 1.0), "kb": ("data", 1000.0),
    "mb": ("data", 1e6), "gb": ("data", 1e9), "tb": ("data", 1e12),
    "kib": ("data", 1024.0), "mib": ("data", 1048576.0), "gib": ("data", 1073741824.0),
    "tib": ("data", 1099511627776.0), "bit": ("data", 0.125),
    # time (second)
    "s": ("time", 1.0), "sec": ("time", 1.0), "second": ("time", 1.0),
    "ms": ("time", 0.001), "min": ("time", 60.0), "minute": ("time", 60.0),
    "h": ("time", 3600.0), "hr": ("time", 3600.0), "hour": ("time", 3600.0),
    "day": ("time", 86400.0), "week": ("time", 604800.0), "year": ("time", 31557600.0),
    # area (m²)
    "m2": ("area", 1.0), "km2": ("area", 1e6), "cm2": ("area", 1e-4),
    "ha": ("area", 10000.0), "hectare": ("area", 10000.0),
    "acre": ("area", 4046.8564224), "ft2": ("area", 0.09290304), "mi2": ("area", 2589988.110336),
    # pressure (pascal)
    "pa": ("pressure", 1.0), "kpa": ("pressure", 1000.0), "bar": ("pressure", 100000.0),
    "psi": ("pressure", 6894.757293), "atm": ("pressure", 101325.0), "mmhg": ("pressure", 133.322387415),
    # energy (joule)
    "j": ("energy", 1.0), "kj": ("energy", 1000.0), "cal": ("energy", 4.184),
    "kcal": ("energy", 4184.0), "wh": ("energy", 3600.0), "kwh": ("energy", 3.6e6),
    # angle (radian)
    "rad": ("angle", 1.0), "deg": ("angle", 0.017453292519943295),
}

_TEMPERATURE_UNITS = {"c", "celsius", "f", "fahrenheit", "k", "kelvin"}

#: Short display symbols used in converted results.
_UNIT_SYMBOLS = {
    "mile": "mi",
    "meter": "m",
    "metre": "m",
    "kilometer": "km",
    "kilometre": "km",
    "foot": "ft",
    "feet": "ft",
    "inch": "in",
    "yard": "yd",
    "gram": "g",
    "kilogram": "kg",
    "pound": "lb",
    "ounce": "oz",
    "liter": "L",
    "litre": "L",
    "gallon": "gal",
    "minute": "min",
    "second": "s",
    "hour": "h",
    "byte": "B",
    "celsius": "°C",
    "fahrenheit": "°F",
    "kelvin": "K",
}


@lru_cache(maxsize=1)
def _load_sympy() -> tuple[Any, Any, tuple]:
    import sympy
    from sympy.parsing.sympy_parser import parse_expr, standard_transformations

    return sympy, parse_expr, standard_transformations


def warm_up() -> None:
    """Load SymPy before the first calculator query."""
    _load_sympy()


def _display_unit(unit: str) -> str:
    return _UNIT_SYMBOLS.get(unit, unit)


def _unit_key(name: str) -> str:
    key = name.strip().lower().replace("°", "").replace(" ", "")
    key = key.replace("²", "2").replace("³", "3")
    return key


def _resolve_unit(name: str) -> str:
    key = _unit_key(name)
    if key in _UNIT_TABLE or key in _TEMPERATURE_UNITS:
        return key
    if key.endswith("s"):
        singular = key[:-1]
        if singular in _UNIT_TABLE or singular in _TEMPERATURE_UNITS:
            return singular
    return key


def _percent_normalise(text: str) -> str:
    if "%" not in text:
        return text
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%\s*of\s*(.+)\s*", text, re.IGNORECASE)
    if match:
        return f"({match.group(1)}/100)*({match.group(2)})"
    match = re.fullmatch(r"\s*(.+?)\s*([+\-])\s*(\d+(?:\.\d+)?)\s*%\s*", text)
    if match:
        base = match.group(1)
        return f"({base}){match.group(2)}(({base})*{match.group(3)}/100)"
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%\s*", text)
    if match:
        return f"({match.group(1)}/100)"
    raise CalculatorError("Unsupported use of % (try '20% of 50' or '50 + 20%')")


def normalise_expression(expression: str) -> str:
    """Replace calculator-friendly symbols with Python/sympy syntax."""
    text = expression.strip()
    if not text:
        raise CalculatorError("Enter an expression")
    text = (
        text.replace("×", "*")
        .replace("÷", "/")
        .replace("−", "-")
        .replace("–", "-")
        .replace("π", "pi")
        .replace("√", "sqrt")
        .replace("²", "**2")
        .replace("³", "**3")
    )
    text = text.replace("^", "**")
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    if text.count(",") == 0 and re.match(r"^-?\d+,\d+$", text.strip()):
        text = text.replace(",", ".")
    text = _percent_normalise(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _local_dict(angle_unit: str, sympy: Any) -> dict[str, Any]:
    degrees = angle_unit == "deg"
    factor = sympy.pi / 180 if degrees else sympy.Integer(1)

    def trig(fn):
        return lambda value: fn(value * factor)

    return {
        "sqrt": sympy.sqrt,
        "cbrt": sympy.cbrt,
        "root": lambda value, n=2: sympy.root(value, n),
        "sin": trig(sympy.sin),
        "cos": trig(sympy.cos),
        "tan": trig(sympy.tan),
        "asin": sympy.asin,
        "acos": sympy.acos,
        "atan": sympy.atan,
        "sinh": sympy.sinh,
        "cosh": sympy.cosh,
        "tanh": sympy.tanh,
        "log": lambda value, base=10: sympy.log(value, base),
        "ln": sympy.log,
        "lg": lambda value: sympy.log(value, 10),
        "log2": lambda value: sympy.log(value, 2),
        "log10": lambda value: sympy.log(value, 10),
        "exp": sympy.exp,
        "abs": sympy.Abs,
        "factorial": sympy.factorial,
        "floor": sympy.floor,
        "ceil": sympy.ceiling,
        "ceiling": sympy.ceiling,
        "round": lambda value: sympy.floor(value + sympy.Rational(1, 2)),
        "sign": sympy.sign,
        "mod": lambda a, b: sympy.Mod(a, b),
        "pi": sympy.pi,
        "e": sympy.E,
        "tau": 2 * sympy.pi,
        "phi": sympy.GoldenRatio,
        "inf": sympy.oo,
        "deg": lambda value: value * sympy.pi / 180,
        "rad": lambda value: value,
    }


def _validate_tokens(text: str) -> None:
    if "__" in text or "`" in text:
        raise CalculatorError("Invalid expression")
    if re.search(r"[A-Za-z_]\s*\.\s*[A-Za-z_]", text):
        raise CalculatorError("Invalid expression")
    for character in "[]{}'\"\\;:=<>&|@#$~":
        if character in text:
            raise CalculatorError(f"Unsupported character: {character}")
    for word in re.findall(r"[A-Za-z_]+", text):
        if word.lower() not in _MATH_WORDS:
            raise CalculatorError(f"Unknown term: {word}")


def format_number(value: Any, precision: int = 10) -> str:
    """Format a sympy number with a sensible number of significant digits."""
    sympy, _, _ = _load_sympy()
    numeric = sympy.N(value, precision + 4)
    if numeric in (sympy.zoo, sympy.nan, sympy.oo, -sympy.oo):
        raise CalculatorError("The result is not a finite number")
    if getattr(numeric, "is_Integer", False):
        return str(int(numeric))
    try:
        as_float = float(numeric)
    except (TypeError, ValueError) as exc:
        raise CalculatorError("The result cannot be displayed as a number") from exc
    if as_float != as_float or as_float in (float("inf"), float("-inf")):
        raise CalculatorError("The result is not a finite number")
    if abs(as_float - round(as_float)) < 1e-12 and abs(as_float) < 1e15:
        return str(int(round(as_float)))
    if as_float == 0:
        return "0"
    if abs(as_float) >= 1e15 or abs(as_float) < 1e-6:
        return f"{as_float:.{max(1, precision - 1)}e}".replace("e+", "e")
    text = f"{as_float:.{precision}g}"
    if "e" in text:
        return text
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def evaluate(expression: str, precision: int = 10, angle_unit: str = "rad") -> str:
    """Safely evaluate a mathematical expression and format the result."""
    prepared = normalise_expression(expression)
    _validate_tokens(prepared)
    sympy, parse_expr, standard_transformations = _load_sympy()
    try:
        parsed = parse_expr(
            prepared,
            local_dict=_local_dict(angle_unit, sympy),
            transformations=standard_transformations,
            evaluate=True,
        )
    except CalculatorError:
        raise
    except Exception as exc:
        raise CalculatorError("Invalid expression") from exc

    if not isinstance(parsed, sympy.Basic) or not parsed.is_number:
        raise CalculatorError("The expression does not evaluate to a number")
    if parsed.has(sympy.zoo):
        raise CalculatorError("Division by zero")
    if parsed.has(sympy.nan):
        raise CalculatorError("The result is not a number")
    if parsed.has(sympy.oo):
        raise CalculatorError("The result is infinite")
    return format_number(parsed, precision)


def looks_like_math(text: str) -> bool:
    """Heuristically decide whether *text* is a mathematical expression."""
    value = (text or "").strip()
    if not value or len(value) > 200:
        return False
    if re.fullmatch(r"[\d.]+[eE][+-]?\d+", value):
        return True
    if re.search(r"\d", value) is None:
        return False
    if re.fullmatch(r"[\d\s.,+\-*/^%()×÷−√]+", value):
        return True
    words = re.findall(r"[A-Za-z_]+", value)
    if not words:
        return False
    if any(word.lower() not in _MATH_WORDS for word in words):
        return False
    return bool(re.search(r"[+\-*/^%()×÷−]", value) or re.search(r"[A-Za-z]+\s*\(", value))


def looks_like_conversion(text: str) -> bool:
    return bool(_CONVERSION_RE.match(text or ""))


def convert_units(text: str, precision: int = 8) -> str:
    """Convert ``"100 km to miles"`` and return e.g. ``"62.13712 mi"``."""
    match = _CONVERSION_RE.match(text or "")
    if not match:
        raise CalculatorError("Usage: 100 km to miles")
    try:
        value = float(match.group(1).replace(",", "."))
    except ValueError as exc:
        raise CalculatorError("The value is not a number") from exc
    source = _resolve_unit(match.group(2))
    target = _resolve_unit(match.group(3))

    if source in _TEMPERATURE_UNITS or target in _TEMPERATURE_UNITS:
        result = _convert_temperature(value, source, target)
        sympy, _, _ = _load_sympy()
        return f"{format_number(sympy.Float(result), precision)} {_display_unit(target)}"

    if source not in _UNIT_TABLE:
        raise CalculatorError(f"Unknown unit: {match.group(2).strip()}")
    if target not in _UNIT_TABLE:
        raise CalculatorError(f"Unknown unit: {match.group(3).strip()}")
    source_dimension, source_factor = _UNIT_TABLE[source]
    target_dimension, target_factor = _UNIT_TABLE[target]
    if source_dimension != target_dimension:
        raise CalculatorError(f"{source} and {target} are not compatible units")
    result = value * source_factor / target_factor
    sympy, _, _ = _load_sympy()
    return f"{format_number(sympy.Float(result), precision)} {_display_unit(target)}"


def _convert_temperature(value: float, source: str, target: str) -> float:
    if source not in _TEMPERATURE_UNITS:
        raise CalculatorError(f"Unknown temperature unit: {source}")
    if target not in _TEMPERATURE_UNITS:
        raise CalculatorError(f"Unknown temperature unit: {target}")
    if source in {"c", "celsius"}:
        celsius = value
    elif source in {"f", "fahrenheit"}:
        celsius = (value - 32) * 5 / 9
    else:
        celsius = value - 273.15
    if target in {"c", "celsius"}:
        return celsius
    if target in {"f", "fahrenheit"}:
        return celsius * 9 / 5 + 32
    return celsius + 273.15


@dataclass
class CalcOutcome:
    ok: bool
    expression: str = ""
    result: str = ""
    error: str = ""

    @property
    def display(self) -> str:
        return self.result if self.ok else self.error


class CalculatorService:
    """Calculator facade with history storage."""

    def __init__(self, config: ConfigManager, db: Database):
        self.config = config
        self.db = db

    @property
    def precision(self) -> int:
        return int(self.config.get("calculator.precision", 10) or 10)

    @property
    def angle_unit(self) -> str:
        return str(self.config.get("calculator.angle_unit", "rad") or "rad")

    def evaluate_text(self, text: str) -> CalcOutcome:
        cleaned = (text or "").strip()
        if not cleaned:
            return CalcOutcome(ok=False, expression=cleaned, error="Enter an expression")
        if looks_like_conversion(cleaned):
            try:
                result = convert_units(cleaned, precision=self.precision)
            except CalculatorError as exc:
                return CalcOutcome(ok=False, expression=cleaned, error=str(exc))
            return CalcOutcome(ok=True, expression=cleaned, result=result)
        try:
            result = evaluate(cleaned, precision=self.precision, angle_unit=self.angle_unit)
        except CalculatorError as exc:
            return CalcOutcome(ok=False, expression=cleaned, error=str(exc))
        return CalcOutcome(ok=True, expression=cleaned, result=result)

    def record(self, outcome: CalcOutcome) -> None:
        if not outcome.ok:
            return
        limit = int(self.config.get("calculator.history_limit", 50) or 0)
        if limit <= 0:
            return
        self.db.add_history("calc", f"{outcome.expression} = {outcome.result}")
        rows = self.db.history("calc", limit + 50)
        for row in rows[limit:]:
            self.db._write("DELETE FROM history WHERE id = ?", (row["id"],))

    def history(self, limit: int = 50) -> list[str]:
        return [row["value"] for row in self.db.history("calc", limit)]

    def clear_history(self) -> None:
        self.db.clear_history(["calc"])


class CalculatorProvider(SearchProvider):
    """Automatic calculation and the ``calc:`` keyword."""

    id = "calculator"
    title = "Calculator"
    keyword = "calc"
    weight = 1.25
    auto = True

    def __init__(self, config, db, hooks, service: CalculatorService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or CalculatorService(config, db)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip()
        if not text:
            return []
        if looks_like_conversion(text):
            outcome = self.service.evaluate_text(text)
        elif looks_like_math(text):
            outcome = self.service.evaluate_text(text)
        else:
            return []

        if not outcome.ok:
            if len(text) >= 3 and text[-1] in "0123456789).":
                return [self._error_result(outcome)]
            return []

        result = outcome.result
        return [
            self.make_result(
                title=result,
                subtitle=f"{outcome.expression}  ·  Enter copies the result",
                category="Calculator",
                score=0.98,
                primary=lambda: self._copy(outcome, notify=True),
                actions=[
                    ResultAction("Copy expression and result", lambda: self._copy_full(outcome)),
                    ResultAction("Open calculator history", lambda: self.hooks.open_tools("calculator")),
                ],
                copy_text=result,
                icon_glyph="=",
                meta={"expression": outcome.expression, "result": result},
            )
        ]

    def _error_result(self, outcome: CalcOutcome) -> SearchResult:
        return self.make_result(
            title="Invalid expression",
            subtitle=outcome.error,
            category="Calculator",
            score=0.5,
            actions=[ResultAction("Open calculator", lambda: self.hooks.open_tools("calculator"))],
            icon_glyph="=",
        )

    def _copy(self, outcome: CalcOutcome, notify: bool = False) -> None:
        self.hooks.copy_text(outcome.result)
        self.service.record(outcome)
        if notify:
            self.hooks.notify(f"Copied {outcome.result}")
        self.hooks.hide_launcher()

    def _copy_full(self, outcome: CalcOutcome) -> None:
        self.hooks.copy_text(f"{outcome.expression} = {outcome.result}")
        self.service.record(outcome)
        self.hooks.notify("Copied expression and result")

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Calculator",
            subtitle="Try: sqrt(144) + 25 * 4  ·  15% of 80  ·  100 km to miles",
            category="Calculator",
            score=1.0,
            primary=lambda: self.hooks.copy_text("sqrt(144) + 25 * 4"),
            icon_glyph="=",
        )


class UnitProvider(SearchProvider):
    """The ``unit:`` keyword for explicit unit conversion."""

    id = "unit"
    title = "Unit conversion"
    keyword = "unit"
    weight = 1.05
    auto = False

    def __init__(self, config, db, hooks, service: CalculatorService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or CalculatorService(config, db)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip()
        if not text:
            return []
        outcome = self.service.evaluate_text(text)
        if not outcome.ok:
            return [
                self.make_result(
                    title="Cannot convert that",
                    subtitle=outcome.error,
                    category="Calculator",
                    score=0.8,
                    icon_glyph="⇄",
                )
            ]
        return [
            self.make_result(
                title=outcome.result,
                subtitle=f"{outcome.expression}  ·  Enter copies the value",
                category="Calculator",
                score=0.95,
                primary=lambda: self.hooks.copy_text(outcome.result),
                actions=[
                    ResultAction(
                        "Copy expression and result",
                        lambda: self.hooks.copy_text(f"{outcome.expression} = {outcome.result}"),
                    )
                ],
                copy_text=outcome.result,
                icon_glyph="⇄",
                meta={"conversion": True},
            )
        ]

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Unit conversion",
            subtitle="Try: 100 km to miles  ·  72 f to c  ·  5 gb to mb",
            category="Calculator",
            score=1.0,
            primary=lambda: self.hooks.fill_query("100 km to miles"),
            icon_glyph="⇄",
        )


__all__ = [
    "CalculatorError",
    "CalculatorService",
    "CalculatorProvider",
    "UnitProvider",
    "CalcOutcome",
    "evaluate",
    "format_number",
    "looks_like_math",
    "looks_like_conversion",
    "convert_units",
    "normalise_expression",
]
