"""Orchestrator agent — coordinates routing and user-facing turns."""

from __future__ import annotations

from typing import Any, Callable

from agent.config import orchestrator_max_iterations
from agent.conversation_loop import ConversationResult, run_conversation_loop


class OrchestratorAgent:
    """Main control agent with a lower iteration budget than subagents."""

    def __init__(
        self,
        llm_call: Callable[[list[dict[str, Any]]], Any],
        max_iterations: int | None = None,
        tool_executor: Callable[[dict[str, Any]], str] | None = None,
    ):
        self.llm_call = llm_call
        self.max_iterations = max_iterations or orchestrator_max_iterations()
        self.tool_executor = tool_executor

    def run_turn(
        self,
        messages: list[dict[str, Any]],
        *,
        prefix_messages: list[dict[str, Any]] | None = None,
        tool_hook=None,
        text_hook=None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> ConversationResult:
        combined = list(prefix_messages or []) + list(messages)
        return run_conversation_loop(
            messages=combined,
            llm_call=self.llm_call,
            tool_executor=self.tool_executor,
            max_iterations=self.max_iterations,
            tool_hook=tool_hook,
            text_hook=text_hook,
            tools=tools,
            tool_choice=tool_choice,
        )
