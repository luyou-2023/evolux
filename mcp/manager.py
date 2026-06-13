"""Lazy MCP server configuration and stdio/HTTP discovery."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from agent.settings import MCPSamplingSettings, Settings, load_settings
from evolux_constants import get_evolux_home
from mcp.http_client import MCPHTTPClient, MCPHTTPError
from mcp.sampling import MCPSamplingConfig, MCPSamplingHandler
from mcp.stdio_client import MCPStdioClient, MCPStdioError
from mcp.subprocess_env import (
    build_stdio_env,
    resolve_stdio_connect_timeout,
    resolve_stdio_cwd,
    resolve_stdio_timeout,
)

logger = logging.getLogger("evolux.mcp")


@dataclass
class MCPServerConfig:
    name: str
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    enabled: bool = True
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    timeout: float = 120.0


class MCPManager:
    """Load MCP configs lazily; connect stdio or HTTP clients on first discovery."""

    def __init__(
        self,
        home: Path | None = None,
        settings: Settings | None = None,
        llm_call: Callable[..., Any] | None = None,
    ):
        self.home = home or get_evolux_home()
        self.settings = settings or load_settings(self.home)
        self.llm_call = llm_call
        self._discovered: dict[str, list[dict[str, Any]]] = {}
        self._clients: dict[str, MCPStdioClient | MCPHTTPClient] = {}
        self._sampling_handlers: dict[str, MCPSamplingHandler] = {}

    def get_mcp_status(self) -> dict[str, Any]:
        """Return sampling audit metrics per MCP server."""
        status: dict[str, Any] = {}
        for name, handler in self._sampling_handlers.items():
            status[name] = {
                "requests": handler.stats.requests,
                "errors": handler.stats.errors,
                "tool_rounds": handler.stats.tool_rounds,
            }
        return status

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
                    env={
                        str(k): str(v)
                        for k, v in (raw.get("env") or {}).items()
                        if isinstance(raw.get("env"), dict)
                    },
                    cwd=str(raw["cwd"]) if raw.get("cwd") not in (None, "") else None,
                    timeout=resolve_stdio_timeout(raw),
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
                self._get_or_create_stdio_client(server_name, config),
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
            return self._get_or_create_stdio_client(server_name, config)
        if config.get("url"):
            return self._get_or_create_http_client(server_name, str(config["url"]))
        return None

    def _get_or_create_stdio_client(self, server_name: str, config: dict[str, Any]) -> MCPStdioClient:
        if server_name not in self._clients:
            command = str(config.get("command") or "")
            args = list(config.get("args") or [])
            handler = self._sampling_handler_for(server_name)
            if handler:
                self._sampling_handlers[server_name] = handler
            self._clients[server_name] = MCPStdioClient(
                command,
                args,
                env=build_stdio_env(config.get("env"), evolux_home=self.home),
                cwd=resolve_stdio_cwd(config, command, args),
                home=self.home,
                sampling_handler=handler,
                timeout=resolve_stdio_timeout(config),
                connect_timeout=resolve_stdio_connect_timeout(config),
            )
        return self._clients[server_name]

    def _sampling_handler_for(self, server_name: str) -> MCPSamplingHandler | None:
        config = self._server_sampling_config(server_name)
        if not config.enabled or not self.llm_call:
            return None
        return MCPSamplingHandler(
            self.llm_call,
            config=config,
            model=self.settings.llm.model,
        )

    def _server_sampling_config(self, server_name: str) -> MCPSamplingConfig:
        raw = self.settings.mcp.servers.get(server_name, {})
        sampling = raw.get("sampling") if isinstance(raw, dict) else None
        if isinstance(sampling, dict):
            return MCPSamplingConfig(
                enabled=bool(sampling.get("enabled", self.settings.mcp.sampling.enabled)),
                max_tool_rounds=int(
                    sampling.get("max_tool_rounds", self.settings.mcp.sampling.max_tool_rounds)
                ),
            )
        return MCPSamplingConfig(
            enabled=self.settings.mcp.sampling.enabled,
            max_tool_rounds=self.settings.mcp.sampling.max_tool_rounds,
        )

    def _get_or_create_http_client(self, server_name: str, url: str) -> MCPHTTPClient:
        if server_name not in self._clients:
            self._clients[server_name] = MCPHTTPClient(url)
        return self._clients[server_name]
