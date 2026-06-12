"""LLM client abstraction — OpenAI-compatible API with mock for tests."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse: ...


@dataclass
class MockLLMClient:
    """Deterministic LLM for tests and offline mode."""

    default_content: str = "Mock LLM response."
    responses: list[LLMResponse] = field(default_factory=list)
    calls: list[list[dict[str, Any]]] = field(default_factory=list, repr=False)

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        self.calls.append(list(messages))
        if self.responses:
            return self.responses.pop(0)
        return LLMResponse(content=self.default_content)


@dataclass
class OpenAICompatibleClient:
    """Minimal OpenAI-compatible chat completions client (stdlib HTTP)."""

    api_key: str
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    timeout: float = 120.0

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if tools:
            payload["tools"] = tools

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API error {exc.code}: {detail}") from exc

        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        tool_calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            fn = raw.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(
                    id=str(raw.get("id", "")),
                    name=str(fn.get("name", "")),
                    arguments=args,
                )
            )
        return LLMResponse(content=message.get("content"), tool_calls=tool_calls)


def llm_call_adapter(client: LLMClient) -> Callable[[list[dict[str, Any]]], Any]:
    """Bridge LLMClient to conversation_loop's duck-typed llm_call."""

    class _AdapterResponse:
        def __init__(self, response: LLMResponse):
            self.content = response.content
            self.tool_calls = [
                {
                    "id": call.id,
                    "name": call.name,
                    "arguments": call.arguments,
                }
                for call in response.tool_calls
            ]

    def _call(messages: list[dict[str, Any]]):
        return _AdapterResponse(client.complete(messages))

    return _call


def create_llm_client(
    *,
    model: str = "gpt-4o-mini",
    base_url: str = "https://api.openai.com/v1",
    api_key: str | None = None,
    mock_content: str = "Configure OPENAI_API_KEY or llm.api_key in ~/.evolux/.env for live responses.",
) -> LLMClient:
    key = api_key or os.environ.get("OPENAI_API_KEY") or os.environ.get("EVOLUX_API_KEY")
    if key:
        return OpenAICompatibleClient(api_key=key, model=model, base_url=base_url)
    return MockLLMClient(default_content=mock_content)
