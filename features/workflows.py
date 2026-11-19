"""Safe, local multi-step workflows for Quick Actions 2.0.

Workflows are structured data, not scripts. They never invoke a shell, eval,
load Python, or execute imported code.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from core.config_manager import ConfigManager
from core.database import Database, DatabaseError
from core.logging_setup import get_logger
from core.models import ResultAction, SearchResult
from core.search_engine import SearchProvider
from core.workers import CancelToken
from core.fuzzy import fuzzy_score
from . import util

log = get_logger(__name__)

WORKFLOW_SCHEMA_VERSION = 1
STEP_TYPES = {"open_folder", "open_url", "launch_app", "copy_text", "run_command"}
MAX_STEPS = 30
MAX_TEXT = 20_000
MAX_IMPORT_BYTES = 1_000_000


def validate_step(step: Any) -> tuple[bool, str]:
    if not isinstance(step, dict):
        return False, "Each workflow step must be an object"
    kind = str(step.get("type", "")).strip()
    if kind not in STEP_TYPES:
        return False, f"Unsupported workflow step: {kind or '(missing type)'}"
    if kind == "open_folder":
        target = str(step.get("path", "")).strip()
        if not target or not Path(target).expanduser().is_dir():
            return False, "Workflow folder step must point to an existing folder"
    elif kind == "open_url":
        url = str(step.get("url", "")).strip()
        if urlsplit(url).scheme.lower() not in {"http", "https"} or not urlsplit(url).hostname:
            return False, "Workflow URLs must start with http:// or https://"
    elif kind == "launch_app":
        executable = str(step.get("executable", "")).strip()
        args = step.get("args", [])
        if not executable or not isinstance(args, list) or len(args) > 64:
            return False, "Application steps need an executable and an argument list"
        if not all(isinstance(arg, str) and len(arg) <= 2048 for arg in args):
            return False, "Application arguments must be strings of at most 2048 characters"
        candidate = Path(executable).expanduser()
        if not (candidate.exists() and candidate.is_file()) and util.which(executable) is None:
            return False, f"Application not found: {executable}"
    elif kind == "copy_text":
        value = step.get("text")
        if not isinstance(value, str) or len(value) > MAX_TEXT:
            return False, f"Copied text must be a string under {MAX_TEXT} characters"
    elif kind == "run_command":
        command = step.get("command")
        args = step.get("args", [])
        if not isinstance(command, str) or not command.strip() or len(command) > 120:
            return False, "Command steps need an existing command key or title"
        if not isinstance(args, list) or len(args) > 64:
            return False, "Command steps accept at most 64 arguments"
        if not all(isinstance(arg, str) and len(arg) <= 2048 for arg in args):
            return False, "Command arguments must be strings of at most 2048 characters"
    return True, ""


def validate_workflow(data: Any) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "Workflow must be an object"
    title = str(data.get("title", "")).strip()
    steps = data.get("steps")
    if not title:
        return False, "A workflow title is required"
    if len(title) > 100:
        return False, "Workflow titles must be 100 characters or fewer"
    if not isinstance(steps, list) or not steps or len(steps) > MAX_STEPS:
        return False, f"Workflows need between 1 and {MAX_STEPS} steps"
    for index, step in enumerate(steps, 1):
        ok, message = validate_step(step)
        if not ok:
            return False, f"Step {index}: {message}"
    return True, ""


class WorkflowService:
    """CRUD, import/export and sequential execution for structured workflows."""

    def __init__(self, config: ConfigManager, db: Database, hooks, command_service=None):
        self.config = config
        self.db = db
        self.hooks = hooks
        self.command_service = command_service

    def workflows(self) -> list[dict[str, Any]]:
        rows = self.db.list_workflows()
        for row in rows:
            row["steps"] = json.loads(row.pop("steps_json"))
        return rows

    def save(self, data: dict[str, Any]) -> tuple[bool, str]:
        ok, message = validate_workflow(data)
        if not ok:
            return False, message
        payload = json.dumps(data["steps"], ensure_ascii=False, separators=(",", ":"))
        self.db.upsert_workflow({
            "id": data.get("id"),
            "title": str(data["title"]).strip(),
            "description": str(data.get("description", "")).strip()[:500],
            "steps_json": payload,
        })
        return True, ""

    def preview(self, workflow: dict[str, Any]) -> tuple[bool, str, list[str]]:
        ok, message = validate_workflow(workflow)
        if not ok:
            return False, message, []
        lines = []
        for index, step in enumerate(workflow["steps"], 1):
            kind = step["type"]
            if kind == "open_folder":
                detail = f"Open folder: {step['path']}"
            elif kind == "open_url":
                detail = f"Open website: {step['url']}"
            elif kind == "launch_app":
                detail = f"Launch app: {step['executable']} {' '.join(step.get('args', []))}".strip()
            elif kind == "copy_text":
                detail = f"Copy text ({len(step['text'])} characters)"
            else:
                detail = f"Run configured command: {step['command']} {' '.join(step.get('args', []))}".strip()
            lines.append(f"{index}. {detail}")
        return True, "", lines

    def delete(self, workflow_id: int) -> None:
        self.db.delete_workflow(workflow_id)

    def export_json(self) -> str:
        return json.dumps({
            "schema_version": WORKFLOW_SCHEMA_VERSION,
            "workflows": [
                {"title": row["title"], "description": row["description"], "steps": row["steps"]}
                for row in self.workflows()
            ],
        }, ensure_ascii=False, indent=2)

    def import_json(self, content: str) -> tuple[bool, str, int]:
        if not isinstance(content, str):
            return False, "Workflow export must be UTF-8 text", 0
        try:
            if len(content.encode("utf-8")) > MAX_IMPORT_BYTES:
                return False, "Workflow export is too large", 0
        except UnicodeEncodeError:
            return False, "Workflow export contains invalid Unicode text", 0
        try:
            payload = json.loads(content)
        except (TypeError, ValueError):
            return False, "The workflow file is not valid JSON", 0
        if not isinstance(payload, dict) or payload.get("schema_version") != WORKFLOW_SCHEMA_VERSION:
            return False, "Unsupported workflow export version", 0
        rows = payload.get("workflows")
        if not isinstance(rows, list) or len(rows) > 100:
            return False, "Workflow export must contain at most 100 workflows", 0
        # Validate the complete import before writing anything.
        for index, row in enumerate(rows, 1):
            ok, message = validate_workflow(row)
            if not ok:
                return False, f"Workflow {index}: {message}", 0
        prepared = [
            {
                "title": str(row["title"]).strip(),
                "description": str(row.get("description", "")).strip()[:500],
                "steps_json": json.dumps(row["steps"], ensure_ascii=False, separators=(",", ":")),
            }
            for row in rows
        ]
        try:
            self.db.insert_workflows_atomic(prepared)
        except DatabaseError as exc:
            log.exception("Workflow import failed")
            return False, str(exc), 0
        return True, "Workflows imported", len(rows)

    def run(
        self,
        workflow: dict[str, Any],
        *,
        token: CancelToken | None = None,
        on_progress: Callable[[int, int, str], None] | None = None,
    ) -> tuple[bool, str, int]:
        ok, message = validate_workflow(workflow)
        if not ok:
            return False, message, 0
        steps = workflow["steps"]
        for index, step in enumerate(steps, 1):
            if token is not None and token.cancelled:
                return False, "Workflow cancelled", index - 1
            kind = step["type"]
            try:
                if kind == "open_folder":
                    success = bool(self.hooks.open_path(step["path"]))
                    detail = "Opened folder" if success else "Could not open folder"
                elif kind == "open_url":
                    success = bool(self.hooks.open_url(step["url"]))
                    detail = "Opened website" if success else "Could not open website"
                elif kind == "launch_app":
                    executable = str(Path(step["executable"]).expanduser())
                    if not Path(executable).exists():
                        executable = util.which(executable) or executable
                    success, detail = util.run_detached([executable, *step.get("args", [])])
                elif kind == "copy_text":
                    success = bool(self.hooks.copy_text(step["text"]))
                    detail = "Copied text" if success else "Could not copy text"
                else:
                    if self.command_service is None:
                        return False, f"Step {index}: command execution is unavailable", index - 1
                    requested = str(step["command"]).casefold()
                    entry = next(
                        (candidate for candidate in self.command_service.entries()
                         if requested in {candidate.key.casefold(), candidate.title.casefold(),
                                          *(alias.casefold() for alias in candidate.aliases)}),
                        None,
                    )
                    if entry is None:
                        return False, f"Step {index}: unknown configured command '{step['command']}'", index - 1
                    if entry.confirmation and not self.hooks.confirm(
                        f"Confirm workflow command: {entry.title}",
                        f"Run {entry.title}?\n\n{entry.description}\n\n"
                        "This step is part of a saved workflow.",
                    ):
                        return False, f"Workflow cancelled at command step {index}", index - 1
                    outcome = self.command_service.run_arguments(entry, list(step.get("args", [])))
                    success, detail = outcome.success, outcome.message
                    if success and outcome.output:
                        self.hooks.show_info(entry.title, outcome.output)
            except Exception as exc:
                log.exception("Workflow step %s failed", index)
                return False, f"Step {index} failed: {exc}", index - 1
            if on_progress is not None:
                try:
                    on_progress(index, len(steps), detail)
                except Exception:
                    log.exception("Workflow progress callback failed")
            if not success:
                return False, f"Step {index} failed: {detail}", index - 1
        return True, f"Completed {len(steps)} steps", len(steps)



class WorkflowProvider(SearchProvider):
    """Explicit flow-keyword search for user-created local workflows."""

    id = "workflows"
    title = "Workflows"
    keyword = "flow"
    weight = 0.95
    auto = False

    def __init__(self, config, db, hooks, service: WorkflowService | None = None):
        super().__init__(config, db, hooks)
        self.service = service or WorkflowService(config, db, hooks)

    def search(self, query: str, limit: int) -> list[SearchResult]:
        text = (query or "").strip()
        rows = self.service.workflows()
        if text:
            scored = [
                (max(
                    fuzzy_score(text, row["title"], typo_tolerance=True),
                    fuzzy_score(text, row.get("description", ""), typo_tolerance=True) * 0.8,
                ), row)
                for row in rows
            ]
            rows = [row for score, row in sorted(scored, key=lambda item: item[0], reverse=True)
                    if score >= 0.35][:limit]
        else:
            rows = rows[:limit]
        return [self._result(row, 0.9 - index * 0.02) for index, row in enumerate(rows)]

    def _result(self, workflow: dict[str, Any], score: float) -> SearchResult:
        return self.make_result(
            title=workflow["title"],
            subtitle=f"{len(workflow['steps'])} steps  ·  {workflow.get('description', '')}",
            category="Workflow",
            score=score,
            primary=lambda: self._run(workflow),
            actions=[
                ResultAction("Edit workflows", lambda: self.hooks.open_tools("workflows")),
                ResultAction("Copy workflow JSON", lambda: self.hooks.copy_text(
                    json.dumps(workflow, ensure_ascii=False, indent=2)
                )),
            ],
            icon_glyph="⇢",
            meta={"workflow": workflow},
        )

    def _run(self, workflow: dict[str, Any]) -> None:
        valid, message, lines = self.service.preview(workflow)
        if not valid:
            self.hooks.notify(message, "error")
            return
        if not self.hooks.confirm(
            f"Run workflow: {workflow['title']}?",
            "The following actions will run in order:\n\n" + "\n".join(lines),
        ):
            return
        ok, message, completed = self.service.run(workflow)
        self.hooks.notify(f"{message} ({completed}/{len(workflow['steps'])})",
                          "info" if ok else "error")
        if ok:
            self.hooks.hide_launcher()

    def empty_help(self) -> SearchResult | None:
        return self.make_result(
            title="No workflows found",
            subtitle="Create a workflow in Tools → Workflows, then search with flow:",
            category="Workflow",
            score=1.0,
            primary=lambda: self.hooks.open_tools("workflows"),
            icon_glyph="⇢",
        )


__all__ = [
    "WORKFLOW_SCHEMA_VERSION", "STEP_TYPES", "MAX_IMPORT_BYTES", "WorkflowService",
    "validate_step", "validate_workflow", "WorkflowProvider",
]
