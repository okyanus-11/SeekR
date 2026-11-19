"""Local task list with due dates, completion and explicit task search."""
from __future__ import annotations

from datetime import date
from typing import Any

from core.config_manager import ConfigManager
from core.database import Database
from core.fuzzy import fuzzy_score
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider


class TaskService:
    def __init__(self, config: ConfigManager, db: Database, hooks):
        self.config = config
        self.db = db
        self.hooks = hooks

    def tasks(self, include_completed: bool = True) -> list[dict[str, Any]]:
        return self.db.list_tasks(include_completed)

    def save(self, data: dict[str, Any]) -> tuple[bool, str]:
        title = str(data.get("title", "")).strip()
        notes = str(data.get("notes", "")).strip()
        due_date = str(data.get("due_date", "") or "").strip()
        if not title:
            return False, "A task title is required"
        if len(title) > 160:
            return False, "Task titles must be 160 characters or fewer"
        if len(notes) > 4000:
            return False, "Task notes must be 4,000 characters or fewer"
        if due_date:
            try:
                date.fromisoformat(due_date)
            except ValueError:
                return False, "Due dates must use YYYY-MM-DD"
        self.db.upsert_task({
            "id": data.get("id"),
            "title": title,
            "notes": notes,
            "due_date": due_date,
            "completed": bool(data.get("completed", False)),
        })
        return True, ""

    def complete(self, task_id: int, completed: bool = True) -> None:
        self.db.set_task_completed(task_id, completed)

    def delete(self, task_id: int) -> None:
        self.db.delete_task(task_id)

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        text = (query or "").strip()
        rows = self.tasks()
        if not text:
            return rows[:limit]
        scored = []
        for row in rows:
            haystack = " ".join((row["title"], row.get("notes", ""), row.get("due_date", "")))
            score = fuzzy_score(text, haystack, typo_tolerance=True)
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [row for score, row in scored[:limit] if score >= 0.35]


class TaskProvider(SearchProvider):
    id = "tasks"
    title = "Tasks"
    keyword = "task"
    weight = 0.9
    auto = False

    def __init__(self, config, db, hooks, service: TaskService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or TaskService(config, db, hooks)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        rows = self.service.search(query, limit)
        return [self._result(row, 0.9 - index * 0.02) for index, row in enumerate(rows)]

    def _result(self, task: dict[str, Any], score: float) -> SearchResult:
        completed = bool(task.get("completed"))
        due = task.get("due_date") or "No due date"
        actions = [
            ResultAction("Reopen task" if completed else "Mark complete",
                         lambda: self._toggle(task, not completed)),
            ResultAction("Manage tasks", lambda: self.hooks.open_tools("tasks")),
        ]
        return self.make_result(
            title=task["title"],
            subtitle=f"{'Completed' if completed else 'Open'}  ·  {due}  ·  {task.get('notes', '')}",
            category="Task",
            score=score,
            primary=lambda: self.hooks.open_tools("tasks"),
            actions=actions,
            copy_text=task["title"],
            icon_glyph="✓" if completed else "○",
            meta={"task": task},
        )

    def _toggle(self, task: dict[str, Any], completed: bool) -> None:
        self.service.complete(int(task["id"]), completed)
        self.hooks.notify("Task completed" if completed else "Task reopened")
        self.hooks.hide_launcher()

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="Task list",
            subtitle="Create and track local tasks in Tools → Tasks",
            category="Task",
            score=1.0,
            primary=lambda: self.hooks.open_tools("tasks"),
            icon_glyph="✓",
        )


__all__ = ["TaskService", "TaskProvider"]
