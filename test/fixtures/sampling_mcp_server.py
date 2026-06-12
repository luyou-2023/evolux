#!/usr/bin/env python3
"""MCP stdio server that requests client sampling during tool execution."""

from __future__ import annotations

import json
import sys


def _send(payload: dict) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def _read() -> dict:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if line in {b"\r\n", b"\n"}:
            break
        key, value = line.decode("ascii").split(":", 1)
        headers[key.strip().lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


def main() -> None:
    while True:
        message = _read()
        method = message.get("method")
        msg_id = message.get("id")

        if method == "initialize":
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}, "sampling": {}},
                        "serverInfo": {"name": "sampling-mcp", "version": "0.0.1"},
                    },
                }
            )
            continue

        if method == "notifications/initialized":
            continue

        if method == "tools/list":
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": [
                            {
                                "name": "ask",
                                "description": "Ask the host LLM via sampling",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"prompt": {"type": "string"}},
                                },
                            }
                        ]
                    },
                }
            )
            continue

        if method == "tools/call":
            params = message.get("params") or {}
            prompt = (params.get("arguments") or {}).get("prompt", "Say hello")
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": 9001,
                    "method": "sampling/createMessage",
                    "params": {
                        "messages": [
                            {
                                "role": "user",
                                "content": {"type": "text", "text": prompt},
                            }
                        ],
                        "maxTokens": 64,
                    },
                }
            )
            sampling_response = _read()
            sampled_text = ""
            result = sampling_response.get("result") or {}
            content = result.get("content") or {}
            if isinstance(content, dict):
                sampled_text = str(content.get("text") or "")
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [{"type": "text", "text": f"sampled:{sampled_text}"}],
                        "isError": False,
                    },
                }
            )
            continue

        if msg_id is not None:
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32601, "message": f"unknown method: {method}"},
                }
            )


if __name__ == "__main__":
    main()
