"""Central tool registry — Hermes-compatible registration and discovery."""

from __future__ import annotations

import ast
import importlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("evolux.tools.registry")

ToolHandler = Callable[..., Any]


@dataclass
class ToolEntry:
    name: str
    toolset: str
    schema: dict[str, Any]
    handler: ToolHandler
    check_fn: Callable[[], bool] | None = None
    description: str = ""


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    def register(
        self,
        name: str,
        handler: ToolHandler | None = None,
        schema: dict[str, Any] | None = None,
        *,
        toolset: str = "builtin",
        check_fn: Callable[[], bool] | None = None,
        description: str = "",
        override: bool = False,
    ) -> None:
        if handler is None or schema is None:
            raise ValueError("handler and schema are required")

        existing = self._tools.get(name)
        if existing and existing.toolset != toolset and not override:
            both_mcp = existing.toolset.startswith("mcp-") and toolset.startswith("mcp-")
            if not both_mcp:
                logger.warning("Tool registration rejected: %s shadowed by %s", name, existing.toolset)
                return

        fn_schema = schema.get("function", schema)
        self._tools[name] = ToolEntry(
            name=name,
            toolset=toolset,
            schema=schema if schema.get("type") == "function" else {"type": "function", "function": fn_schema},
            handler=handler,
            check_fn=check_fn,
            description=description or str(fn_schema.get("description", "")),
        )

    def deregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get_entry(self, name: str) -> ToolEntry | None:
        return self._tools.get(name)

    def get_schema(self, name: str) -> dict[str, Any] | None:
        entry = self._tools.get(name)
        return entry.schema if entry else None

    def list_schemas(self) -> list[dict[str, Any]]:
        return [entry.schema for entry in self._tools.values()]

    def get_definitions(self, tool_names: set[str]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for name in sorted(tool_names):
            entry = self._tools.get(name)
            if not entry:
                continue
            if entry.check_fn and not _safe_check(entry.check_fn):
                continue
            result.append(entry.schema)
        return result

    def dispatch(self, name: str, arguments: dict[str, Any] | str, **kwargs: Any) -> str:
        entry = self._tools.get(name)
        if not entry:
            return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
        if isinstance(arguments, str):
            arguments = json.loads(arguments) if arguments else {}
        try:
            result = entry.handler(arguments or {}, **kwargs)
        except TypeError:
            result = entry.handler(arguments or {})
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False)

    def clear(self) -> None:
        self._tools.clear()
        try:
            from tools import discover as discover_mod

            discover_mod._LOADED = False
        except ImportError:
            pass


registry = ToolRegistry()


def register(name: str, handler: ToolHandler, schema: dict[str, Any], **kwargs: Any) -> None:
    """Backward-compatible helper used by legacy tool modules."""
    registry.register(name, handler, schema, **kwargs)


def get_schema(name: str) -> dict[str, Any] | None:
    return registry.get_schema(name)


def list_schemas() -> list[dict[str, Any]]:
    return registry.list_schemas()


def dispatch(name: str, arguments: dict[str, Any] | str, **kwargs: Any) -> str:
    return registry.dispatch(name, arguments, **kwargs)


def clear_registry() -> None:
    registry.clear()


def tool_error(message: str, **extra: Any) -> str:
    payload = {"success": False, "error": message}
    payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def _safe_check(fn: Callable[[], bool]) -> bool:
    try:
        return bool(fn())
    except Exception:
        return False


def _module_registers_tools(module_path: Path) -> bool:
    try:
        source = module_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module_path))
    except (OSError, SyntaxError):
        return False
    for stmt in tree.body:
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            continue
        func = stmt.value.func
        if isinstance(func, ast.Attribute) and func.attr == "register":
            return True
        if isinstance(func, ast.Name) and func.id == "register":
            return True
    return False


def discover_builtin_tools(tools_dir: Path | None = None) -> list[str]:
    """Import Hermes-style self-registering tool modules."""
    tools_path = tools_dir or Path(__file__).resolve().parent
    skip = {
        "__init__.py",
        "registry.py",
        "orchestrator_tools.py",
        "discover.py",
    }
    module_names = [
        f"tools.{path.stem}"
        for path in sorted(tools_path.glob("*.py"))
        if path.name not in skip and _module_registers_tools(path)
    ]
    imported: list[str] = []
    for mod_name in module_names:
        try:
            importlib.import_module(mod_name)
            imported.append(mod_name)
        except Exception as exc:
            logger.warning("Could not import tool module %s: %s", mod_name, exc)
    return imported
