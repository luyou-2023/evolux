"""midscenejs_luke UI automation tools for Evolux ui-automation-expert."""

from __future__ import annotations

import json
from typing import Any

from tools.midscene_luke_bridge import (
    engine_installed,
    init_ui_test_project,
    luke_engine_root,
    run_luke_workflow,
    run_playwright_test,
)
from tools.registry import registry, tool_error


def _parse_steps(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return [dict(item) for item in raw if isinstance(item, dict)]
    if isinstance(raw, str) and raw.strip():
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [dict(item) for item in parsed if isinstance(item, dict)]
    return []


def midscene_luke_run_tool(arguments: dict[str, Any]) -> str:
    url = str(arguments.get("url") or "").strip()
    steps = _parse_steps(arguments.get("steps"))
    if not url and not steps:
        return tool_error("url or steps is required")
    payload = {
        "url": url,
        "headless": arguments.get("headless", True),
        "viewport": arguments.get("viewport") or {"width": 1280, "height": 768},
        "steps": steps,
        "stopOnError": arguments.get("stop_on_error", True),
        "agentOptions": arguments.get("agent_options") or {},
    }
    result = run_luke_workflow(payload, timeout=int(arguments.get("timeout") or 180))
    return json.dumps(result, ensure_ascii=False)


def midscene_luke_init_tool(_arguments: dict[str, Any]) -> str:
    path = init_ui_test_project()
    return json.dumps({"success": True, "workspace": str(path), "engine": "midscenejs_luke"}, ensure_ascii=False)


def midscene_luke_run_test_tool(arguments: dict[str, Any]) -> str:
    spec = str(arguments.get("spec") or "e2e/smoke.spec.mjs")
    result = run_playwright_test(spec, timeout=int(arguments.get("timeout") or 300))
    return json.dumps(result, ensure_ascii=False)


def midscene_luke_status_tool(_arguments: dict[str, Any]) -> str:
    root = luke_engine_root()
    return json.dumps(
        {
            "engine": "midscenejs_luke",
            "installed": engine_installed(root),
            "root": str(root),
            "apis": ["aiAct", "aiQuery", "aiAssert", "aiTap", "aiInput", "aiWaitFor"],
        },
        ensure_ascii=False,
    )


def check_midscene_luke_requirements() -> bool:
    import shutil

    return bool(shutil.which("node"))


registry.register(
    "midscene_luke_run",
    lambda args: midscene_luke_run_tool(args),
    {
        "type": "function",
        "function": {
            "name": "midscene_luke_run",
            "description": (
                "Run midscenejs_luke vision-driven UI workflow (Playwright). "
                "Steps: act, tap, input, wait, query, assert, boolean, number, string, locate, goto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "headless": {"type": "boolean", "default": True},
                    "timeout": {"type": "integer", "default": 180},
                    "steps": {"type": "array", "items": {"type": "object"}},
                },
            },
        },
    },
    toolset="midscene-luke",
    check_fn=check_midscene_luke_requirements,
)

registry.register(
    "midscene_luke_init_project",
    lambda args: midscene_luke_init_tool(args),
    {
        "type": "function",
        "function": {
            "name": "midscene_luke_init_project",
            "description": "Scaffold ~/.evolux/ui-tests with midscenejs_luke Playwright fixture.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    toolset="midscene-luke",
    check_fn=check_midscene_luke_requirements,
)

registry.register(
    "midscene_luke_run_playwright_test",
    lambda args: midscene_luke_run_test_tool(args),
    {
        "type": "function",
        "function": {
            "name": "midscene_luke_run_playwright_test",
            "description": "Run Playwright spec using midscenejs_luke fixture under ~/.evolux/ui-tests.",
            "parameters": {
                "type": "object",
                "properties": {
                    "spec": {"type": "string", "default": "e2e/smoke.spec.mjs"},
                    "timeout": {"type": "integer", "default": 300},
                },
            },
        },
    },
    toolset="midscene-luke",
    check_fn=check_midscene_luke_requirements,
)

registry.register(
    "midscene_luke_status",
    lambda args: midscene_luke_status_tool(args),
    {
        "type": "function",
        "function": {
            "name": "midscene_luke_status",
            "description": "Check midscenejs_luke engine installation.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    toolset="midscene-luke",
)
