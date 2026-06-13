"""MCP JSON-RPC client over stdio (Content-Length framing)."""

from __future__ import annotations

import json
import logging
import os
import queue
import subprocess
import threading
from pathlib import Path
from typing import Any, IO

from evolux_constants import get_evolux_home
from mcp.sampling import MCPSamplingError, MCPSamplingHandler

logger = logging.getLogger("evolux.mcp.stdio")

MCP_PROTOCOL_VERSION = "2024-11-05"

_stderr_log_handle: IO[str] | None = None
_stderr_log_lock = threading.Lock()


def _get_mcp_stderr_sink(home: Path | None = None) -> IO[str]:
    """Redirect MCP subprocess stderr to a log file (avoids PIPE deadlock)."""
    global _stderr_log_handle
    with _stderr_log_lock:
        if _stderr_log_handle is not None:
            return _stderr_log_handle
        base = home or get_evolux_home()
        try:
            log_dir = base / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            _stderr_log_handle = open(log_dir / "mcp-stderr.log", "a", encoding="utf-8")
        except OSError as exc:
            logger.debug("Failed to open MCP stderr log, using devnull: %s", exc)
            _stderr_log_handle = open(os.devnull, "w", encoding="utf-8")
        return _stderr_log_handle


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
        home: Path | None = None,
        sampling_handler: MCPSamplingHandler | None = None,
        timeout: float = 120.0,
        connect_timeout: float = 60.0,
    ):
        self.command = command
        self.args = list(args or [])
        self.env = env
        self.cwd = cwd
        self.home = home
        self.sampling_handler = sampling_handler
        self.timeout = timeout
        self.connect_timeout = connect_timeout
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

        env = dict(self.env) if self.env is not None else os.environ.copy()
        stderr_sink = _get_mcp_stderr_sink(self.home)
        stderr_sink.write(f"\n--- MCP subprocess: {self.command} {' '.join(self.args)} ---\n")
        stderr_sink.flush()

        self._proc = subprocess.Popen(
            [self.command, *self.args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_sink,
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
            response = response_queue.get(timeout=self.connect_timeout if method == "initialize" else self.timeout)
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
                stderr_tail = _read_stderr_log_tail(self.home)
                raise MCPStdioError(f"MCP server closed connection. stderr={stderr_tail}")
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


def _read_stderr_log_tail(home: Path | None = None, *, max_chars: int = 500) -> str:
    base = home or get_evolux_home()
    path = base / "logs" / "mcp-stderr.log"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-max_chars:]
