import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from agent.conversation_loop import ConversationResult, run_conversation_loop
from agent.iteration_budget import IterationBudget


@dataclass
class LLMResponse:
    content: str | None
    tool_calls: list[dict[str, Any]]


def test_conversation_loop_returns_on_text_response():
    calls = {"n": 0}

    def llm_call(messages: list[dict[str, Any]]) -> LLMResponse:
        calls["n"] += 1
        return LLMResponse(content="done", tool_calls=[])

    result = run_conversation_loop(
        messages=[{"role": "user", "content": "hi"}],
        llm_call=llm_call,
        max_iterations=5,
    )
    assert result.content == "done"
    assert calls["n"] == 1


def test_conversation_loop_executes_tools_until_done():
    step = {"n": 0}

    def llm_call(messages: list[dict[str, Any]]) -> LLMResponse:
        if step["n"] == 0:
            step["n"] += 1
            return LLMResponse(
                content=None,
                tool_calls=[{"id": "1", "name": "echo", "arguments": {"x": 1}}],
            )
        return LLMResponse(content="finished", tool_calls=[])

    def tool_executor(tool_call: dict[str, Any]) -> str:
        return f"ok:{tool_call['name']}"

    result = run_conversation_loop(
        messages=[{"role": "user", "content": "run"}],
        llm_call=llm_call,
        tool_executor=tool_executor,
        max_iterations=5,
    )
    assert result.content == "finished"
    assert step["n"] == 1


def test_conversation_loop_summarizes_when_budget_exhausted():
    def llm_call(messages: list[dict[str, Any]]) -> LLMResponse:
        return LLMResponse(
            content=None,
            tool_calls=[{"id": "1", "name": "noop", "arguments": {}}],
        )

    result = run_conversation_loop(
        messages=[{"role": "user", "content": "loop"}],
        llm_call=llm_call,
        tool_executor=lambda _: "ok",
        max_iterations=2,
    )
    assert result.exhausted is True
    assert "iteration limit" in (result.content or "").lower()


def test_conversation_loop_passes_tool_choice_to_llm():
    captured: dict[str, Any] = {}

    def llm_call(messages: list[dict[str, Any]], **kwargs: Any) -> LLMResponse:
        captured.update(kwargs)
        return LLMResponse(content="done", tool_calls=[])

    run_conversation_loop(
        messages=[{"role": "user", "content": "hi"}],
        llm_call=llm_call,
        max_iterations=3,
        tool_choice="none",
    )
    assert captured.get("tool_choice") == "none"


def test_conversation_loop_executes_multiple_tools_in_parallel():
    executed: list[str] = []
    lock = threading.Lock()
    step = {"n": 0}

    def llm_call(messages: list[dict[str, Any]]) -> LLMResponse:
        if step["n"] == 0:
            step["n"] += 1
            return LLMResponse(
                content=None,
                tool_calls=[
                    {"id": "1", "name": "slow_a", "arguments": {}},
                    {"id": "2", "name": "slow_b", "arguments": {}},
                ],
            )
        return LLMResponse(content="finished", tool_calls=[])

    def tool_executor(tool_call: dict[str, Any]) -> str:
        time.sleep(0.08)
        with lock:
            executed.append(tool_call["name"])
        return f"ok:{tool_call['name']}"

    start = time.monotonic()
    result = run_conversation_loop(
        messages=[{"role": "user", "content": "run"}],
        llm_call=llm_call,
        tool_executor=tool_executor,
        max_iterations=5,
    )
    elapsed = time.monotonic() - start

    assert result.content == "finished"
    assert set(executed) == {"slow_a", "slow_b"}
    assert elapsed < 0.14
