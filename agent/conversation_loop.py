"""Shared LLM ↔ tool conversation loop for orchestrator and subagents."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from agent.tool_calls import parse_tool_call
from agent.tool_hooks import ToolCallHook, wrap_tool_executor
from agent.turn_cancel import is_turn_cancelled


class LLMCallable(Protocol):
    def __call__(self, messages: list[dict[str, Any]], /, **kwargs: Any) -> Any: ...


class ToolExecutor(Protocol):
    def __call__(self, tool_call: dict[str, Any]) -> str: ...


@dataclass
class ConversationResult:
    content: str | None
    messages: list[dict[str, Any]]
    iterations_used: int
    exhausted: bool = False
    plain_reply: bool = False
    interactive_card: dict | None = None


def run_conversation_loop(
    messages: list[dict[str, Any]],
    llm_call: LLMCallable,
    max_iterations: int,
    tool_executor: ToolExecutor | None = None,
    on_exhausted: Callable[[list[dict[str, Any]]], str] | None = None,
    tool_hook: ToolCallHook | None = None,
    text_hook: Callable[[str], None] | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
) -> ConversationResult:
    """Run the agent loop until a text response or iteration budget is hit."""
    from agent.iteration_budget import IterationBudget

    history = list(messages)
    budget = IterationBudget(max_total=max_iterations)
    iterations_used = 0
    executor = wrap_tool_executor(tool_executor, tool_hook) if tool_executor else None

    while budget.remaining > 0:
        if is_turn_cancelled():
            return ConversationResult(
                content="已停止当前任务。",
                messages=history,
                iterations_used=iterations_used,
                exhausted=False,
                plain_reply=True,
            )
        if not budget.consume():
            break
        iterations_used += 1
        llm_kwargs: dict[str, Any] = {}
        if tools:
            llm_kwargs["tools"] = tools
        if tool_choice is not None:
            llm_kwargs["tool_choice"] = tool_choice
        if text_hook:
            llm_kwargs["on_text_delta"] = text_hook
        try:
            response = llm_call(history, **llm_kwargs)
        except TypeError:
            llm_kwargs.pop("on_text_delta", None)
            try:
                response = llm_call(history, **llm_kwargs)
            except TypeError:
                response = llm_call(history)

        tool_calls = getattr(response, "tool_calls", None) or []
        content = getattr(response, "content", None)

        if tool_calls:
            if executor is None:
                history.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
                for call in tool_calls:
                    name, _ = parse_tool_call(call)
                    history.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id", ""),
                            "content": "error: no tool executor configured",
                        }
                    )
                continue

            history.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
            tool_results = _execute_tool_calls(tool_calls, executor)
            history.extend(tool_results)
            continue

        return ConversationResult(
            content=content,
            messages=history,
            iterations_used=iterations_used,
            exhausted=False,
        )

    summarizer = on_exhausted or _default_exhausted_summary
    summary = summarizer(history)
    return ConversationResult(
        content=summary,
        messages=history,
        iterations_used=iterations_used,
        exhausted=True,
    )


def _default_exhausted_summary(messages: list[dict[str, Any]]) -> str:
    return "Stopped: iteration limit reached before producing a final answer."


def _execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    executor: ToolExecutor,
) -> list[dict[str, Any]]:
    def _run(call: dict[str, Any]) -> dict[str, Any]:
        name, arguments = parse_tool_call(call)
        result = executor({"id": call.get("id", ""), "name": name, "arguments": arguments})
        return {
            "role": "tool",
            "tool_call_id": call.get("id", ""),
            "content": result,
        }

    if len(tool_calls) <= 1:
        return [_run(call) for call in tool_calls]

    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(len(tool_calls), 8)) as pool:
        futures = {pool.submit(_run, call): str(call.get("id", "")) for call in tool_calls}
        for future in as_completed(futures):
            item = future.result()
            results[item["tool_call_id"]] = item
    return [results[str(call.get("id", ""))] for call in tool_calls]
