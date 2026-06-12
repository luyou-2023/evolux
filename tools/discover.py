"""Load all built-in Evolux tool modules once."""

from __future__ import annotations

import importlib

from tools.registry import discover_builtin_tools, registry

_LOADED = False
_LOADED_MODULES: list[str] = []


def ensure_tools_loaded() -> list[str]:
    global _LOADED
    if _LOADED and registry._tools:
        return _LOADED_MODULES
    if _LOADED and not registry._tools:
        for mod_name in _LOADED_MODULES:
            importlib.reload(importlib.import_module(mod_name))
        return _LOADED_MODULES

    modules = discover_builtin_tools()
    _LOADED_MODULES[:] = modules
    _LOADED = True
    return modules
