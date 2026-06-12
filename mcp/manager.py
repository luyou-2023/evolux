"""Lazy MCP server configuration and stdio/HTTP discovery."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.settings import Settings, load_settings
from evolux_constants import get_evolux_home
from mcp.http_client import MCPHTTPClient, MCPHTTPError
from mcp.stdio_client import MCPStdioClient, MCPStdioError

logger = logging.getLogger("evolux.mcp")


@dataclass
class MCPServerConfig:
    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    enabled: bool = True


class MCPManager:
    """Load MCP configs lazily; connect stdio or HTTP clients on first discovery."""

    def __init__(self, home: Path | None = None, settings: Settings | None = None):
        self.home = home or get_evolux_home()
        self.settings = settings or load_settings(self.home)
        self._discovered: dict[str, list[dict[str, Any]]] = {}
        self._clients: dict[str, MCPStdioClient | MCPHTTPClient] = {}

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

    def register_server(self, name: str, config: dict[str, Any], *, rediscover: bool = True) -> None:
        """Register or override an MCP server at runtime (e.g. ACP session servers)."""
        self.settings.mcp.servers[name] = dict(config)
        if rediscover:
            self._discovered.pop(name, None)
            client = self._clients.pop(name, None)
            if client:
                client.close()

    def discover_tools(self, server_name: str) -> list[dict[str, Any]]:
        if server_name in self._discovered:
            return self._discovered[server_name]

        config = self.settings.mcp.servers.get(server_name)
        if not config or not config.get("enabled", True):
            logger.warning("MCP server not configured: %s", server_name)
            self._discovered[server_name] = []
            return []

        command = config.get("command")
        if command:
            tools = self._discover_with_client(
                server_name,
                self._get_or_create_stdio_client(server_name, str(command), list(config.get("args") or [])),
            )
        elif config.get("url"):
            tools = self._discover_with_client(
                server_name,
                self._get_or_create_http_client(server_name, str(config["url"])),
            )
        else:
            tools = []

        self._discovered[server_name] = tools
        return tools

    def call_tool(self, server_name: str, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        client = self._get_client(server_name)
        if not client:
            raise KeyError(f"MCP server unavailable: {server_name}")
        return client.call_tool(tool_name, arguments)

    def close(self) -> None:
        for client in self._clients.values():
            client.close()
        self._clients.clear()

    def _discover_with_client(
        self,
        server_name: str,
        client: MCPStdioClient | MCPHTTPClient,
    ) -> list[dict[str, Any]]:
        try:
            raw_tools = client.list_tools()
        except (MCPStdioError, MCPHTTPError) as exc:
            logger.warning("MCP discovery failed for %s: %s", server_name, exc)
            return []
        return self._normalize_tools(server_name, raw_tools)

    def _normalize_tools(self, server_name: str, raw_tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for item in raw_tools:
            name = str(item.get("name", ""))
            if not name:
                continue
            tools.append(
                {
                    "name": f"mcp_{server_name}_{name}",
                    "mcp_server": server_name,
                    "mcp_tool": name,
                    "description": str(item.get("description") or f"MCP tool {name}"),
                    "inputSchema": item.get("inputSchema") or {"type": "object", "properties": {}},
                }
            )
        logger.info("MCP discovered %d tools for %s", len(tools), server_name)
        return tools

    def _get_client(self, server_name: str) -> MCPStdioClient | MCPHTTPClient | None:
        if server_name in self._clients:
            return self._clients[server_name]
        config = self.settings.mcp.servers.get(server_name)
        if not config:
            return None
        if config.get("command"):
            return self._get_or_create_stdio_client(
                server_name,
                str(config["command"]),
                list(config.get("args") or []),
            )
        if config.get("url"):
            return self._get_or_create_http_client(server_name, str(config["url"]))
        return None

    def _get_or_create_stdio_client(self, server_name: str, command: str, args: list[str]) -> MCPStdioClient:
        if server_name not in self._clients:
            self._clients[server_name] = MCPStdioClient(command, args)
        return self._clients[server_name]

    def _get_or_create_http_client(self, server_name: str, url: str) -> MCPHTTPClient:
        if server_name not in self._clients:
            self._clients[server_name] = MCPHTTPClient(url)
        return self._clients[server_name]
