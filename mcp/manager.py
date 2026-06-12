"""Lazy MCP server configuration and discovery."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.settings import Settings, load_settings
from evolux_constants import get_evolux_home

logger = logging.getLogger("evolux.mcp")


@dataclass
class MCPServerConfig:
    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    enabled: bool = True


class MCPManager:
    """Load MCP configs lazily; discovery is deferred until first use."""

    def __init__(self, home: Path | None = None, settings: Settings | None = None):
        self.home = home or get_evolux_home()
        self.settings = settings or load_settings(self.home)
        self._discovered: dict[str, list[dict[str, Any]]] = {}

    def list_servers(self) -> list[MCPServerConfig]:
        servers = []
        for name, raw in self.settings.mcp.servers.items():
            if not isinstance(raw, dict):
                continue
            servers.append(
                MCPServerConfig(
                    name=name,
                    command=raw.get("command"),
                    args=list(raw.get("args") or []),
                    url=raw.get("url"),
                    enabled=bool(raw.get("enabled", True)),
                )
            )
        return servers

    def discover_tools(self, server_name: str) -> list[dict[str, Any]]:
        if server_name in self._discovered:
            return self._discovered[server_name]

        config = self.settings.mcp.servers.get(server_name)
        if not config:
            logger.warning("MCP server not configured: %s", server_name)
            self._discovered[server_name] = []
            return []

        # Phase 4: spawn stdio/HTTP MCP client. For now expose config metadata only.
        tools = [
            {
                "name": f"mcp_{server_name}_placeholder",
                "description": f"Placeholder for MCP server {server_name} (wire client in Phase 4.1)",
            }
        ]
        self._discovered[server_name] = tools
        logger.info("MCP discovery stub loaded %d tools for %s", len(tools), server_name)
        return tools
