"""MCP JSON-RPC client over Streamable HTTP."""

from __future__ import annotations

import json
import logging
import ssl
import threading
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger("evolux.mcp.http")

MCP_PROTOCOL_VERSION = "2024-11-05"


class MCPHTTPError(RuntimeError):
    pass


class MCPHTTPClient:
    """Exchange MCP JSON-RPC messages over HTTP POST (Streamable HTTP subset)."""

    def __init__(self, url: str, *, timeout: float = 30.0):
        self.url = url.rstrip("/") + "/"
        self.timeout = timeout
        self._session_id: str | None = None
        self._lock = threading.Lock()
        self._next_id = 1
        self._initialized = False

    def connect(self) -> None:
        if self._initialized:
            return
        self._initialize_session()

    def list_tools(self) -> list[dict[str, Any]]:
        self.connect()
        result = self._request("tools/list", {})
        tools = result.get("tools") if isinstance(result, dict) else None
        return list(tools or [])

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        self.connect()
        result = self._request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        return dict(result) if isinstance(result, dict) else {"content": result}

    def close(self) -> None:
        self._session_id = None
        self._initialized = False

    def _initialize_session(self) -> None:
        result = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "evolux", "version": "0.4.0"},
            },
            allow_no_body=True,
        )
        if not isinstance(result, dict):
            raise MCPHTTPError("invalid initialize response")
        self._notify("notifications/initialized", {})
        self._initialized = True
        logger.debug("MCP HTTP initialized: %s", result.get("serverInfo"))

    def _request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        allow_no_body: bool = False,
    ) -> Any:
        with self._lock:
            message_id = self._next_id
            self._next_id += 1
            payload = {
                "jsonrpc": "2.0",
                "id": message_id,
                "method": method,
                "params": params,
            }
            status, headers, body = self._post(payload)
            if status == 202 and allow_no_body:
                return {}
            if not body:
                if allow_no_body:
                    return {}
                raise MCPHTTPError(f"empty HTTP response for {method}")
            response = json.loads(body.decode("utf-8"))
            if not isinstance(response, dict):
                raise MCPHTTPError("invalid MCP JSON response")
            session_id = headers.get("mcp-session-id")
            if session_id:
                self._session_id = session_id
            if response.get("id") not in (None, message_id):
                raise MCPHTTPError(f"unexpected response id: {response.get('id')}")
            if "error" in response:
                err = response["error"]
                raise MCPHTTPError(f"{method} failed: {err.get('message', err)}")
            return response.get("result")

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._post({"jsonrpc": "2.0", "method": method, "params": params})

    def _post(self, payload: dict[str, Any]) -> tuple[int, dict[str, str], bytes]:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        request = urllib.request.Request(
            self.url,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout, context=_ssl_context()) as response:
                raw_headers = {
                    key.lower(): value
                    for key, value in response.headers.items()
                }
                body = response.read()
                return response.status, raw_headers, body
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise MCPHTTPError(f"HTTP {exc.code}: {detail}") from exc


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()
