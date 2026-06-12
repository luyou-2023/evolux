"""Register MCP discovered tools into the central registry (Hermes mcp_tool alignment)."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.manager import MCPManager
from tools.registry import registry

logger = logging.getLogger("evolux.mcp.registry")


def sync_mcp_tools(manager: MCPManager, server_name: str | None = None) -> list[str]:
    """Discover MCP tools and register them with toolset prefix mcp-{server}."""
    registered: list[str] = []
    servers = [server_name] if server_name else [s.name for s in manager.list_servers() if s.enabled]
    for name in servers:
        toolset = f"mcp-{name}"
        for tool in manager.discover_tools(name):
            tool_name = str(tool.get("name", ""))
            native = str(tool.get("mcp_tool", ""))
            if not tool_name or not native:
                continue

            input_schema = tool.get("inputSchema") or {"type": "object", "properties": {}}

            def _make_handler(server: str, native_tool: str):
                def _handler(args: dict[str, Any], **_kw: Any) -> str:
                    result = manager.call_tool(server, native_tool, args or {})
                    return json.dumps(result, ensure_ascii=False)

                return _handler

            schema = {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": str(tool.get("description") or f"MCP tool {native}"),
                    "parameters": input_schema,
                },
            }
            registry.register(
                tool_name,
                _make_handler(name, native),
                schema,
                toolset=toolset,
                override=True,
            )
            registered.append(tool_name)
            logger.debug("registered MCP tool %s under %s", tool_name, toolset)
    return registered
