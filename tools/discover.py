"""Load all built-in Evolux tool modules once."""

from __future__ import annotations

from tools.registry import discover_builtin_tools

_LOADED = False


def ensure_tools_loaded() -> list[str]:
    global _LOADED
    if _LOADED:
        return []
    modules = discover_builtin_tools()
    _LOADED = True
    return modules
