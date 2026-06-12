"""Route MCP discovered tools through MCPManager."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.manager import MCPManager

logger = logging.getLogger("evolux.mcp.tools")


class MCPToolRouter:
    """Lazy map evolux-facing MCP tool names to server + native tool."""

    def __init__(self, manager: MCPManager):
        self.manager = manager
        self._tool_map: dict[str, tuple[str, str]] = {}
        self._discovered = False

    def discover(self, server_names: list[str] | None = None) -> list[dict[str, Any]]:
        self._ensure_discovered(server_names)
        return [{"name": name, "server": s, "tool": t} for name, (s, t) in self._tool_map.items()]

    def dispatch(self, tool_name: str, arguments: dict[str, Any] | str) -> str:
        self._ensure_discovered()
        if tool_name not in self._tool_map:
            return json.dumps({"error": f"unknown MCP tool: {tool_name}"}, ensure_ascii=False)

        if isinstance(arguments, str):
            arguments = json.loads(arguments) if arguments else {}

        server_name, native_tool = self._tool_map[tool_name]
        try:
            result = self.manager.call_tool(server_name, native_tool, dict(arguments or {}))
            return json.dumps(result, ensure_ascii=False)
        except Exception as exc:
            logger.warning("MCP tool call failed %s: %s", tool_name, exc)
            return json.dumps({"error": str(exc)}, ensure_ascii=False)

    def _ensure_discovered(self, server_names: list[str] | None = None) -> None:
        if self._discovered and server_names is None:
            return

        targets = server_names
        if targets is None:
            targets = [s.name for s in self.manager.list_servers() if s.enabled]

        for server_name in targets:
            for tool in self.manager.discover_tools(server_name):
                name = str(tool.get("name", ""))
                native = str(tool.get("mcp_tool", ""))
                server = str(tool.get("mcp_server", server_name))
                if name and native:
                    self._tool_map[name] = (server, native)

        self._discovered = True
