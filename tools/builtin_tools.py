"""Built-in tools registered at import time."""

from __future__ import annotations

import platform as py_platform
from datetime import datetime, timezone

from tools.registry import register


def _echo(args: dict) -> dict:
    return {"echo": args.get("message", "")}


def _system_info(_args: dict) -> dict:
    return {
        "platform": py_platform.system(),
        "python": py_platform.python_version(),
        "utc": datetime.now(timezone.utc).isoformat(),
    }


register(
    "echo",
    _echo,
    {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo a message back (builtin debug tool).",
            "parameters": {
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        },
    },
)

register(
    "system_info",
    _system_info,
    {
        "type": "function",
        "function": {
            "name": "system_info",
            "description": "Return basic host and runtime information.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
)
