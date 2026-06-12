"""Self-registering tool registry."""

from __future__ import annotations

import json
from typing import Any, Callable

ToolHandler = Callable[[dict[str, Any]], Any]

_REGISTRY: dict[str, tuple[ToolHandler, dict[str, Any]]] = {}


def register(name: str, handler: ToolHandler, schema: dict[str, Any]) -> None:
    _REGISTRY[name] = (handler, schema)


def get_schema(name: str) -> dict[str, Any] | None:
    entry = _REGISTRY.get(name)
    return entry[1] if entry else None


def list_schemas() -> list[dict[str, Any]]:
    return [schema for _, schema in _REGISTRY.values()]


def dispatch(name: str, arguments: dict[str, Any] | str) -> str:
    if name not in _REGISTRY:
        return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
    if isinstance(arguments, str):
        arguments = json.loads(arguments) if arguments else {}
    handler, _ = _REGISTRY[name]
    result = handler(arguments or {})
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


def clear_registry() -> None:
    _REGISTRY.clear()
