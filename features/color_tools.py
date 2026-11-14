"""Color conversion utilities and provider."""

from __future__ import annotations

from core.config_manager import ConfigManager
from core.database import Database
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider

from .developer_tools import ToolError, color_formats

log = get_logger(__name__)


class ColorProvider(SearchProvider):
    """The ``color`` keyword."""

    id = "color"
    title = "Color tools"
    keyword = "color"
    weight = 0.85
    auto = False

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip()
        if not text:
            return [self._picker_result(1.0)]
        try:
            formats = color_formats(text)
        except ToolError:
            return [
                self.make_result(
                    title=f"Cannot read “{text}” as a color",
                    subtitle="Use #RRGGBB, rgb(255, 136, 0) or hsl(30, 100%, 50%)",
                    category="Color",
                    score=0.8,
                    primary=lambda: self.hooks.open_tools("color"),
                    icon_glyph="◉",
                ),
                self._picker_result(0.7),
            ]
        rows = [
            ("HEX " + formats["hex"], "Hexadecimal color value", formats["hex"]),
            ("RGB " + formats["rgb"], "Red, green, blue components", formats["rgb"]),
            ("HSL " + formats["hsl"], "Hue, saturation, lightness", formats["hsl"]),
            ("HSV " + formats["hsv"], "Hue, saturation, value", formats["hsv"]),
            ("Decimal " + formats["decimal"], "24-bit integer color value", formats["decimal"]),
        ]
        results = [
            self.make_result(
                title=title,
                subtitle=f"{subtitle}  ·  Enter copies",
                category="Color",
                score=0.95 - index * 0.03,
                primary=lambda value=value: self._copy(value),
                copy_text=value,
                icon_glyph="◉",
                meta={"color": formats["hex"]},
            )
            for index, (title, subtitle, value) in enumerate(rows)
        ]
        results.append(self._picker_result(0.75))
        return results[:limit]

    def _picker_result(self, score: float) -> SearchResult:
        return self.make_result(
            title="Pick a color…",
            subtitle="Open the color picker with HEX, RGB, HSL and HSV values",
            category="Color",
            score=score,
            primary=lambda: self.hooks.open_tools("color"),
            actions=[ResultAction("Copy white", lambda: self.hooks.copy_text("#ffffff"))],
            icon_glyph="◉",
        )

    def _copy(self, value: str) -> None:
        self.hooks.copy_text(value)
        self.hooks.notify(f"Copied {value}")
        self.hooks.hide_launcher()

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Color converter",
            subtitle="Try: color: #ff8800  ·  color: rgb(20, 120, 90)",
            category="Color",
            score=1.0,
            primary=lambda: self.hooks.open_tools("color"),
            icon_glyph="◉",
        )


__all__ = ["ColorProvider"]
