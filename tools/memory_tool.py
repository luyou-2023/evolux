"""Hermes-aligned persistent memory tool."""

from __future__ import annotations

import json
from pathlib import Path

from agent.memory_manager import MemoryManager
from evolux_constants import get_evolux_home
from tools.registry import registry, tool_error

ENTRY_DELIMITER = "\n§\n"


def _target_path(home: Path, assistant_id: str, target: str) -> Path:
    manager = MemoryManager(home=home, assistant_id=assistant_id)
    directory = manager._memories_dir()
    directory.mkdir(parents=True, exist_ok=True)
    filename = "USER.md" if target == "user" else "MEMORY.md"
    return directory / filename


def _read_entries(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if ENTRY_DELIMITER in text:
        return [part.strip() for part in text.split(ENTRY_DELIMITER) if part.strip()]
    return [text]


def _write_entries(path: Path, entries: list[str]) -> None:
    path.write_text(ENTRY_DELIMITER.join(entries), encoding="utf-8")


def memory_tool(
    *,
    action: str,
    target: str = "memory",
    content: str | None = None,
    old_text: str | None = None,
    home: Path | None = None,
    assistant_id: str = "default",
) -> str:
    base = home or get_evolux_home()
    path = _target_path(base, assistant_id, target)
    entries = _read_entries(path)

    if action == "add":
        if not content:
            return tool_error("content is required for add")
        entries.append(content.strip())
        _write_entries(path, entries)
        return json.dumps({"success": True, "action": "add", "target": target, "entry_count": len(entries)})

    if action == "replace":
        if not old_text or not content:
            return tool_error("old_text and content are required for replace")
        replaced = False
        for idx, entry in enumerate(entries):
            if old_text in entry:
                entries[idx] = content.strip()
                replaced = True
                break
        if not replaced:
            return tool_error("no matching entry for old_text")
        _write_entries(path, entries)
        return json.dumps({"success": True, "action": "replace", "target": target, "entry_count": len(entries)})

    if action == "remove":
        if not old_text:
            return tool_error("old_text is required for remove")
        new_entries = [entry for entry in entries if old_text not in entry]
        if len(new_entries) == len(entries):
            return tool_error("no matching entry for old_text")
        _write_entries(path, new_entries)
        return json.dumps({"success": True, "action": "remove", "target": target, "entry_count": len(new_entries)})

    if action == "read":
        return json.dumps(
            {
                "success": True,
                "action": "read",
                "target": target,
                "entries": entries,
                "entry_count": len(entries),
            },
            ensure_ascii=False,
        )

    return tool_error(f"unknown action: {action}")


MEMORY_SCHEMA = {
    "name": "memory",
    "description": (
        "Save durable MEMORY.md / USER.md notes that persist across sessions (Hermes-compatible)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["add", "replace", "remove", "read"]},
            "target": {"type": "string", "enum": ["memory", "user"]},
            "content": {"type": "string"},
            "old_text": {"type": "string"},
        },
        "required": ["action", "target"],
    },
}


registry.register(
    "memory",
    lambda args, **kw: memory_tool(
        action=args.get("action", "read"),
        target=args.get("target", "memory"),
        content=args.get("content"),
        old_text=args.get("old_text"),
        assistant_id=kw.get("assistant_id", "default"),
    ),
    MEMORY_SCHEMA,
    toolset="memory",
)
