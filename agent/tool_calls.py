"""Normalize tool call payloads between LLM API and executor formats."""

from __future__ import annotations

import json
from typing import Any


def parse_tool_call(tool_call: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    name = str(tool_call.get("name") or "")
    arguments = tool_call.get("arguments", {})
    fn = tool_call.get("function")
    if isinstance(fn, dict):
        name = name or str(fn.get("name") or "")
        arguments = fn.get("arguments", arguments)
    if isinstance(arguments, str):
        arguments = json.loads(arguments) if arguments else {}
    if not isinstance(arguments, dict):
        arguments = {}
    return name, arguments
