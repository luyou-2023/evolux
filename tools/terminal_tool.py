"""Hermes-aligned local terminal execution."""

from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

from evolux_constants import get_evolux_home
from tools.registry import registry, tool_error

MAX_TIMEOUT = 120
_BLOCKED_PATTERNS = ("rm -rf /", "mkfs", ":(){ :|:& };:")


def _resolve_cwd(cwd: str | None) -> Path:
    base = Path(cwd).expanduser() if cwd else get_evolux_home()
    return base.resolve()


def terminal_tool(*, command: str, cwd: str | None = None, timeout: int = 60) -> str:
    command = (command or "").strip()
    if not command:
        return tool_error("command is required")
    lowered = command.lower()
    if any(pattern in lowered for pattern in _BLOCKED_PATTERNS):
        return tool_error("command blocked by safety policy")

    workdir = _resolve_cwd(cwd)
    workdir.mkdir(parents=True, exist_ok=True)
    timeout = max(1, min(int(timeout), MAX_TIMEOUT))

    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(workdir),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return tool_error(f"command timed out after {timeout}s")

    return json.dumps(
        {
            "success": completed.returncode == 0,
            "command": command,
            "cwd": str(workdir),
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-8000:],
            "stderr": completed.stderr[-4000:],
            "session_id": str(uuid.uuid4()),
        },
        ensure_ascii=False,
    )


def check_terminal_requirements() -> bool:
    return True


TERMINAL_SCHEMA = {
    "name": "terminal",
    "description": "Execute a shell command locally (Hermes-compatible subset).",
    "parameters": {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string"},
            "timeout": {"type": "integer"},
        },
        "required": ["command"],
    },
}

registry.register(
    "terminal",
    lambda args, **_: terminal_tool(
        command=str(args.get("command", "")),
        cwd=args.get("cwd"),
        timeout=int(args.get("timeout", 60)),
    ),
    TERMINAL_SCHEMA,
    toolset="terminal",
    check_fn=check_terminal_requirements,
)
