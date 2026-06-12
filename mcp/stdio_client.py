"""MCP JSON-RPC client over stdio (Content-Length framing)."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from typing import Any

logger = logging.getLogger("evolux.mcp.stdio")

MCP_PROTOCOL_VERSION = "2024-11-05"


class MCPStdioError(RuntimeError):
    pass


class MCPStdioClient:
    """Spawn an MCP server subprocess and exchange JSON-RPC messages."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        *,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ):
        self.command = command
        self.args = list(args or [])
        self.env = env
        self.cwd = cwd
        self._proc: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()
        self._next_id = 1
        self._initialized = False

    def connect(self) -> None:
        if self._proc and self._proc.poll() is None:
            return

        env = os.environ.copy()
        if self.env:
            env.update(self.env)

        self._proc = subprocess.Popen(
            [self.command, *self.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=self.cwd,
        )
        self._initialized = False
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
        proc = self._proc
        self._proc = None
        self._initialized = False
        if not proc:
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)

    def _initialize_session(self) -> None:
        result = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "evolux", "version": "0.3.0"},
            },
        )
        if not isinstance(result, dict):
            raise MCPStdioError("invalid initialize response")
        self._notify("notifications/initialized", {})
        self._initialized = True
        logger.debug("MCP initialized: %s", result.get("serverInfo"))

    def _request(self, method: str, params: dict[str, Any]) -> Any:
        with self._lock:
            if not self._proc or self._proc.poll() is not None:
                raise MCPStdioError("MCP process is not running")

            message_id = self._next_id
            self._next_id += 1
            payload = {
                "jsonrpc": "2.0",
                "id": message_id,
                "method": method,
                "params": params,
            }
            self._write_message(payload)
            response = self._read_message()
            if response.get("id") != message_id:
                raise MCPStdioError(f"unexpected response id: {response.get('id')}")
            if "error" in response:
                err = response["error"]
                raise MCPStdioError(f"{method} failed: {err.get('message', err)}")
            return response.get("result")

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        with self._lock:
            if not self._proc or self._proc.poll() is not None:
                raise MCPStdioError("MCP process is not running")
            self._write_message({"jsonrpc": "2.0", "method": method, "params": params})

    def _write_message(self, payload: dict[str, Any]) -> None:
        assert self._proc and self._proc.stdin
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
        self._proc.stdin.write(header + data)
        self._proc.stdin.flush()

    def _read_message(self) -> dict[str, Any]:
        assert self._proc and self._proc.stdout
        headers: dict[str, str] = {}
        while True:
            line = self._proc.stdout.readline()
            if not line:
                stderr = ""
                if self._proc.stderr:
                    stderr = self._proc.stderr.read().decode("utf-8", errors="replace")
                raise MCPStdioError(f"MCP server closed connection. stderr={stderr[:500]}")
            if line in {b"\r\n", b"\n"}:
                break
            key, value = line.decode("ascii", errors="replace").split(":", 1)
            headers[key.strip().lower()] = value.strip()

        length = int(headers.get("content-length", "0"))
        body = self._proc.stdout.read(length)
        if not body:
            raise MCPStdioError("empty MCP response body")
        parsed = json.loads(body.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise MCPStdioError("invalid MCP JSON response")
        return parsed
