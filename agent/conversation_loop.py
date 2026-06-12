"""Shared LLM ↔ tool conversation loop for orchestrator and subagents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


class LLMCallable(Protocol):
    def __call__(self, messages: list[dict[str, Any]]) -> Any: ...


class ToolExecutor(Protocol):
    def __call__(self, tool_call: dict[str, Any]) -> str: ...


@dataclass
class ConversationResult:
    content: str | None
    messages: list[dict[str, Any]]
    iterations_used: int
    exhausted: bool = False


def run_conversation_loop(
    messages: list[dict[str, Any]],
    llm_call: LLMCallable,
    max_iterations: int,
    tool_executor: ToolExecutor | None = None,
    on_exhausted: Callable[[list[dict[str, Any]]], str] | None = None,
) -> ConversationResult:
    """Run the agent loop until a text response or iteration budget is hit."""
    from agent.iteration_budget import IterationBudget

    history = list(messages)
    budget = IterationBudget(max_total=max_iterations)
    iterations_used = 0

    while budget.remaining > 0:
        if not budget.consume():
            break
        iterations_used += 1
        response = llm_call(history)

        tool_calls = getattr(response, "tool_calls", None) or []
        content = getattr(response, "content", None)

        if tool_calls:
            if tool_executor is None:
                history.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
                for call in tool_calls:
                    history.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.get("id", ""),
                            "name": call.get("name", ""),
                            "content": "error: no tool executor configured",
                        }
                    )
                continue

            history.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
            for call in tool_calls:
                result = tool_executor(call)
                history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("id", ""),
                        "name": call.get("name", ""),
                        "content": result,
                    }
                )
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
