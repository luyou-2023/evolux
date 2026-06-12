"""Domain expert subagent — executes delegated tasks."""

from __future__ import annotations

from typing import Any, Callable

from agent.config import subagent_max_iterations
from agent.conversation_loop import ConversationResult, run_conversation_loop


class SubAgent:
    """Single-domain execution agent with a higher iteration budget."""

    def __init__(
        self,
        agent_id: str,
        llm_call: Callable[[list[dict[str, Any]]], Any],
        max_iterations: int | None = None,
        system_prompt: str = "",
        skill_instructions: str = "",
        tool_executor: Callable[[dict[str, Any]], str] | None = None,
    ):
        self.agent_id = agent_id
        self.llm_call = llm_call
        self.max_iterations = max_iterations or subagent_max_iterations()
        self.system_prompt = system_prompt
        self.skill_instructions = skill_instructions
        self.tool_executor = tool_executor

    def run_task(self, task: str, context_slice: str = "", skill_instructions: str = "") -> ConversationResult:
        messages: list[dict[str, Any]] = []
        system_parts = [self.system_prompt, self.skill_instructions, skill_instructions]
        system_content = "\n\n".join(part for part in system_parts if part).strip()
        if system_content:
            messages.append({"role": "system", "content": system_content})
        user_content = task if not context_slice else f"{task}\n\nContext:\n{context_slice}"
        messages.append({"role": "user", "content": user_content})
        return run_conversation_loop(
            messages=messages,
            llm_call=self.llm_call,
            tool_executor=self.tool_executor,
            max_iterations=self.max_iterations,
        )
