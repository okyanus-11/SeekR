"""Data models shared by providers and the UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass(slots=True)
class ResultAction:
    """A secondary action that can be triggered for a search result."""

    label: str
    callback: Callable[[], None]
    hint: str = ""
    shortcut: str = ""


@dataclass
class SearchResult:
    """One row in the launcher result list."""

    title: str
    subtitle: str = ""
    category: str = "General"
    provider: str = ""
    score: float = 0.0
    primary: Optional[Callable[[], None]] = None
    actions: list[ResultAction] = field(default_factory=list)
    copy_text: Optional[str] = None
    icon_path: Optional[str] = None
    icon_glyph: str = ""
    meta: dict[str, Any] = field(default_factory=dict)

    def all_actions(self) -> list[ResultAction]:
        """Primary action first, followed by the secondary actions."""
        actions: list[ResultAction] = []
        if self.primary is not None:
            actions.append(ResultAction("Open", self.primary))
        actions.extend(self.actions)
        return actions

    def execute(self, action_index: int | None = None) -> bool:
        """Run the primary action or the action at *action_index*."""
        if action_index is not None:
            actions = self.actions
            if 0 <= action_index < len(actions):
                actions[action_index].callback()
                return True
            return False
        if self.primary is not None:
            self.primary()
            return True
        if self.actions:
            self.actions[0].callback()
            return True
        return False

    def sort_key(self) -> tuple[float, int]:
        return (-self.score, 0 if self.category == "Calculator" else 1)


__all__ = ["ResultAction", "SearchResult"]
