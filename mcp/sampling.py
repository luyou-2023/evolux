"""Handle MCP server-initiated sampling/createMessage requests."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("evolux.mcp.sampling")


class MCPSamplingError(RuntimeError):
    pass


@dataclass
class MCPSamplingConfig:
    enabled: bool = True
    max_tool_rounds: int = 3


@dataclass
class MCPSamplingStats:
    requests: int = 0
    errors: int = 0
    tool_rounds: int = 0


class MCPSamplingHandler:
    """Bridge MCP sampling requests to the host Evolux LLM."""

    def __init__(
        self,
        llm_call: Callable[..., Any],
        *,
        config: MCPSamplingConfig | None = None,
        model: str = "evolux",
    ):
        self.llm_call = llm_call
        self.config = config or MCPSamplingConfig()
        self.model = model
        self.stats = MCPSamplingStats()

    def create_message(self, params: dict[str, Any]) -> dict[str, Any]:
        if not self.config.enabled:
            raise MCPSamplingError("MCP sampling is disabled")

        self.stats.requests += 1
        messages = normalize_sampling_messages(params.get("messages") or [])
        tools = params.get("tools")
        llm_kwargs: dict[str, Any] = {}
        if tools:
            llm_kwargs["tools"] = tools

        rounds = 0
        while True:
            rounds += 1
            if rounds > self.config.max_tool_rounds:
                raise MCPSamplingError("MCP sampling exceeded max_tool_rounds")
            self.stats.tool_rounds += 1
            try:
                response = self.llm_call(messages, **llm_kwargs)
            except TypeError:
                response = self.llm_call(messages)
            except Exception as exc:
                self.stats.errors += 1
                raise MCPSamplingError(str(exc)) from exc

            tool_calls = getattr(response, "tool_calls", None) or []
            content = getattr(response, "content", None)
            if not tool_calls:
                text = content or ""
                return {
                    "role": "assistant",
                    "content": {"type": "text", "text": text},
                    "model": self.model,
                    "stopReason": "endTurn",
                }

            messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
            for call in tool_calls:
                name = _tool_name(call)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "content": json.dumps({"error": "tools unavailable during MCP sampling"}),
                    }
                )


def normalize_sampling_messages(raw_messages: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "user")
        content = item.get("content")
        if isinstance(content, dict):
            text = content.get("text") or json.dumps(content, ensure_ascii=False)
        else:
            text = str(content or "")
        normalized.append({"role": role, "content": text})
    return normalized


def _tool_name(call: dict[str, Any]) -> str:
    fn = call.get("function")
    if isinstance(fn, dict):
        return str(fn.get("name") or "")
    return str(call.get("name") or "")
