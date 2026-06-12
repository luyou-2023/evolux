"""LLM client abstraction — OpenAI-compatible API with mock for tests."""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key_env": "OPENAI_API_KEY",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
}


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
            with _urlopen(request, timeout=self.timeout) as response:
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

    def stream_complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        *,
        on_delta: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {"model": self.model, "messages": messages, "stream": True}
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
        content_parts: list[str] = []
        try:
            with _urlopen(request, timeout=self.timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    chunk = json.loads(data_str)
                    delta = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")
                    if not delta:
                        continue
                    content_parts.append(delta)
                    if on_delta:
                        on_delta(delta)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM API error {exc.code}: {detail}") from exc

        return LLMResponse(content="".join(content_parts) or None)


def _ssl_context() -> ssl.SSLContext:
    """Build TLS context; prefer certifi bundle (macOS Python often lacks system CAs)."""
    if os.environ.get("EVOLUX_SSL_INSECURE", "").lower() in {"1", "true", "yes"}:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _urlopen(request: urllib.request.Request, timeout: float):
    """Open URL; default direct connect to avoid broken local HTTPS proxies."""
    if os.environ.get("EVOLUX_USE_SYSTEM_PROXY", "").lower() in {"1", "true", "yes"}:
        return urllib.request.urlopen(request, timeout=timeout)

    https_handler = urllib.request.HTTPSHandler(context=_ssl_context())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), https_handler)
    return opener.open(request, timeout=timeout)


def resolve_provider_defaults(
    provider: str,
    *,
    model: str | None = None,
    base_url: str | None = None,
) -> tuple[str, str]:
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["openai"])
    return (
        model or preset["model"],
        base_url or preset["base_url"],
    )


def resolve_api_key(provider: str, explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    preset = PROVIDER_PRESETS.get(provider, PROVIDER_PRESETS["openai"])
    env_names = [preset["api_key_env"], "EVOLUX_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"]
    seen: set[str] = set()
    for name in env_names:
        if name in seen:
            continue
        seen.add(name)
        value = os.environ.get(name)
        if value:
            return value
    return None


def llm_call_adapter(
    client: LLMClient,
) -> Callable[..., Any]:
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

    def _call(messages: list[dict[str, Any]], *, on_text_delta: Callable[[str], None] | None = None):
        if on_text_delta and isinstance(client, OpenAICompatibleClient):
            response = client.stream_complete(messages, on_delta=on_text_delta)
        else:
            response = client.complete(messages)
        return _AdapterResponse(response)

    return _call


def create_llm_client(
    *,
    provider: str = "openai",
    model: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    mock_content: str = "Configure DEEPSEEK_API_KEY or llm settings in ~/.evolux/.env for live responses.",
) -> LLMClient:
    resolved_model, resolved_base_url = resolve_provider_defaults(provider, model=model, base_url=base_url)
    key = resolve_api_key(provider, api_key)
    if key:
        return OpenAICompatibleClient(api_key=key, model=resolved_model, base_url=resolved_base_url)
    return MockLLMClient(default_content=mock_content)
