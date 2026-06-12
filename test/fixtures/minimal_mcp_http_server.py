#!/usr/bin/env python3
"""Minimal MCP Streamable HTTP server for integration tests."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable


class _MCPHTTPHandler(BaseHTTPRequestHandler):
    session_id = "test-mcp-session"

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        message = json.loads(raw.decode("utf-8"))
        method = message.get("method")
        msg_id = message.get("id")

        if method == "initialize":
            payload = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "minimal-mcp-http", "version": "0.0.1"},
                },
            }
        elif method == "notifications/initialized":
            self.send_response(202)
            self.end_headers()
            return
        elif method == "tools/list":
            payload = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echo text back",
                            "inputSchema": {
                                "type": "object",
                                "properties": {"text": {"type": "string"}},
                            },
                        }
                    ]
                },
            }
        elif method == "tools/call":
            params = message.get("params") or {}
            text = (params.get("arguments") or {}).get("text", "")
            payload = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": f"echo:{text}"}],
                    "isError": False,
                },
            }
        elif msg_id is not None:
            payload = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"unknown method: {method}"},
            }
        else:
            self.send_response(202)
            self.end_headers()
            return

        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Mcp-Session-Id", self.session_id)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start_server() -> tuple[str, Callable[[], None]]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MCPHTTPHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    url = f"http://{host}:{port}/"

    def stop() -> None:
        server.shutdown()
        thread.join(timeout=2)

    return url, stop


if __name__ == "__main__":
    url, stop = start_server()
    print(url)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        stop()
