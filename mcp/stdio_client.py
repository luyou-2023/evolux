"""MCP JSON-RPC client over stdio (Content-Length framing)."""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
from typing import Any

from mcp.sampling import MCPSamplingError, MCPSamplingHandler

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
        sampling_handler: MCPSamplingHandler | None = None,
        timeout: float = 120.0,
    ):
        self.command = command
        self.args = list(args or [])
        self.env = env
        self.cwd = cwd
        self.sampling_handler = sampling_handler
        self.timeout = timeout
        self._proc: subprocess.Popen[bytes] | None = None
        self._io_lock = threading.Lock()
        self._pending_lock = threading.Lock()
        self._next_id = 1
        self._initialized = False
        self._pending: dict[int, queue.Queue[dict[str, Any]]] = {}
        self._reader_thread: threading.Thread | None = None
        self._reader_stop = threading.Event()

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
        self._reader_stop.clear()
        self._start_reader()
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
        self._reader_stop.set()
        proc = self._proc
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2)
        self._reader_thread = None
        self._proc = None
        self._initialized = False
        with self._pending_lock:
            self._pending.clear()
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
        capabilities: dict[str, Any] = {}
        if self.sampling_handler and self.sampling_handler.config.enabled:
            capabilities["sampling"] = {}
        result = self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": capabilities,
                "clientInfo": {"name": "evolux", "version": "0.4.0"},
            },
        )
        if not isinstance(result, dict):
            raise MCPStdioError("invalid initialize response")
        self._notify("notifications/initialized", {})
        self._initialized = True
        logger.debug("MCP initialized: %s", result.get("serverInfo"))

    def _request(self, method: str, params: dict[str, Any]) -> Any:
        if not self._proc or self._proc.poll() is not None:
            raise MCPStdioError("MCP process is not running")

        with self._io_lock:
            message_id = self._next_id
            self._next_id += 1

        response_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
        with self._pending_lock:
            self._pending[message_id] = response_queue

        payload = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": method,
            "params": params,
        }
        self._write_message(payload)
        try:
            response = response_queue.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise MCPStdioError(f"timeout waiting for {method}") from exc
        finally:
            with self._pending_lock:
                self._pending.pop(message_id, None)

        if "error" in response:
            err = response["error"]
            raise MCPStdioError(f"{method} failed: {err.get('message', err)}")
        return response.get("result")

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        if not self._proc or self._proc.poll() is not None:
            raise MCPStdioError("MCP process is not running")
        self._write_message({"jsonrpc": "2.0", "method": method, "params": params})

    def _write_message(self, payload: dict[str, Any]) -> None:
        with self._io_lock:
            assert self._proc and self._proc.stdin
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
            self._proc.stdin.write(header + data)
            self._proc.stdin.flush()

    def _start_reader(self) -> None:
        if self._reader_thread and self._reader_thread.is_alive():
            return
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def _reader_loop(self) -> None:
        while not self._reader_stop.is_set():
            if not self._proc or self._proc.poll() is not None:
                break
            try:
                message = self._read_message()
            except MCPStdioError:
                break

            method = message.get("method")
            msg_id = message.get("id")
            if method and msg_id is not None:
                if method == "sampling/createMessage":
                    self._handle_sampling_request(message)
                continue

            if msg_id is None:
                continue
            with self._pending_lock:
                pending = self._pending.get(int(msg_id))
            if pending is not None:
                pending.put(message)

    def _handle_sampling_request(self, message: dict[str, Any]) -> None:
        msg_id = message.get("id")
        params = message.get("params") or {}
        if not self.sampling_handler:
            payload = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": "sampling not supported"},
            }
        else:
            try:
                result = self.sampling_handler.create_message(params)
                payload = {"jsonrpc": "2.0", "id": msg_id, "result": result}
            except MCPSamplingError as exc:
                self.sampling_handler.stats.errors += 1
                payload = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32000, "message": str(exc)},
                }
        self._write_message(payload)

    def _read_message(self) -> dict[str, Any]:
        proc = self._proc
        if not proc or not proc.stdout:
            raise MCPStdioError("MCP process is not running")
        headers: dict[str, str] = {}
        while True:
            line = proc.stdout.readline()
            if not line:
                stderr = ""
                if proc.stderr:
                    stderr = proc.stderr.read().decode("utf-8", errors="replace")
                raise MCPStdioError(f"MCP server closed connection. stderr={stderr[:500]}")
            if line in {b"\r\n", b"\n"}:
                break
            key, value = line.decode("ascii", errors="replace").split(":", 1)
            headers[key.strip().lower()] = value.strip()

        length = int(headers.get("content-length", "0"))
        body = proc.stdout.read(length)
        if not body:
            raise MCPStdioError("empty MCP response body")
        parsed = json.loads(body.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise MCPStdioError("invalid MCP JSON response")
        return parsed
