"""Hermes-aligned file read/write tools scoped to EVOLUX_HOME."""

from __future__ import annotations

import json
from pathlib import Path

from evolux_constants import get_evolux_home
from tools.registry import registry, tool_error


def _resolve_path(raw_path: str) -> Path:
    home = get_evolux_home().resolve()
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = home / path
    resolved = path.resolve()
    if home not in resolved.parents and resolved != home:
        raise ValueError("path must stay under EVOLUX_HOME")
    return resolved


def read_file(*, path: str, offset: int = 1, limit: int | None = None) -> str:
    try:
        resolved = _resolve_path(path)
    except ValueError as exc:
        return tool_error(str(exc))
    if not resolved.exists():
        return tool_error(f"file not found: {path}")
    lines = resolved.read_text(encoding="utf-8").splitlines()
    start = max(offset - 1, 0)
    end = start + limit if limit is not None else len(lines)
    chunk = lines[start:end]
    numbered = "\n".join(f"{start + idx + 1}|{line}" for idx, line in enumerate(chunk))
    return json.dumps(
        {
            "success": True,
            "path": str(resolved),
            "content": numbered,
            "total_lines": len(lines),
        },
        ensure_ascii=False,
    )


def write_file(*, path: str, content: str) -> str:
    try:
        resolved = _resolve_path(path)
    except ValueError as exc:
        return tool_error(str(exc))
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return json.dumps({"success": True, "path": str(resolved), "message": "written"}, ensure_ascii=False)


READ_FILE_SCHEMA = {
    "name": "read_file",
    "description": "Read a text file under EVOLUX_HOME with optional line window.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
        },
        "required": ["path"],
    },
}

WRITE_FILE_SCHEMA = {
    "name": "write_file",
    "description": "Write a text file under EVOLUX_HOME.",
    "parameters": {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["path", "content"],
    },
}

registry.register(
    "read_file",
    lambda args, **_: read_file(
        path=str(args.get("path", "")),
        offset=int(args.get("offset", 1)),
        limit=int(args["limit"]) if args.get("limit") is not None else None,
    ),
    READ_FILE_SCHEMA,
    toolset="file",
)
registry.register(
    "write_file",
    lambda args, **_: write_file(path=str(args.get("path", "")), content=str(args.get("content", ""))),
    WRITE_FILE_SCHEMA,
    toolset="file",
)
