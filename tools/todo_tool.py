"""Simple todo list tool (Hermes-compatible shape)."""

from __future__ import annotations

import json
from pathlib import Path

from evolux_constants import get_evolux_home
from tools.registry import registry

_TODOS: dict[str, list[dict]] = {}


def _store_path(home: Path) -> Path:
    return home / "state" / "todos.json"


def _load(home: Path) -> list[dict]:
    path = _store_path(home)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save(home: Path, items: list[dict]) -> None:
    path = _store_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def todo_tool(*, todos: list[dict] | None = None) -> str:
    home = get_evolux_home()
    if todos is None:
        items = _load(home)
    else:
        items = todos
        _save(home, items)
    summary = {
        "completed": sum(1 for item in items if item.get("status") == "completed"),
        "in_progress": sum(1 for item in items if item.get("status") == "in_progress"),
        "pending": sum(1 for item in items if item.get("status") == "pending"),
    }
    return json.dumps({"success": True, "todos": items, "summary": summary}, ensure_ascii=False)


TODO_SCHEMA = {
    "name": "todo",
    "description": "Maintain a structured todo list for multi-step work.",
    "parameters": {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "content": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed", "cancelled"],
                        },
                    },
                },
            }
        },
    },
}

registry.register("todo", lambda args, **_: todo_tool(todos=args.get("todos")), TODO_SCHEMA, toolset="todo")
