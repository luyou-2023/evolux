"""EvoluxAgent facade — stable entry point for orchestrator runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from agent.agent_registry import AgentRegistry
from agent.orchestrator import OrchestratorAgent
from agent.subagent import SubAgent
from evolux_constants import get_evolux_home
from evolux_state import SessionDB


class EvoluxAgent:
    """Facade wiring SessionDB, AgentRegistry, orchestrator and subagents."""

    def __init__(
        self,
        llm_call: Callable[[list[dict[str, Any]]], Any],
        home: Path | None = None,
        assistant_id: str = "default",
        tool_executor: Callable[[dict[str, Any]], str] | None = None,
    ):
        self.home = home or get_evolux_home()
        self.assistant_id = assistant_id
        self.session_db = SessionDB(home=self.home)
        self.agent_registry = AgentRegistry(home=self.home)
        self.orchestrator = OrchestratorAgent(
            llm_call=llm_call,
            tool_executor=tool_executor,
        )

    def run_orchestrator_turn(
        self,
        session_key: str,
        user_message: str,
        platform: str = "cli",
    ):
        session_id = self.session_db.get_or_create_session(
            session_key=session_key,
            assistant_id=self.assistant_id,
            platform=platform,
        )
        history = [{"role": m["role"], "content": m["content"]} for m in self.session_db.get_messages(session_id)]
        history.append({"role": "user", "content": user_message})

        result = self.orchestrator.run_turn(history)
        if result.content:
            self.session_db.append_message(session_id, "user", user_message)
            self.session_db.append_message(session_id, "assistant", result.content)
        return result

    def create_subagent(
        self,
        agent_id: str,
        llm_call: Callable[[list[dict[str, Any]]], Any] | None = None,
        system_prompt: str = "",
        tool_executor: Callable[[dict[str, Any]], str] | None = None,
    ) -> SubAgent:
        return SubAgent(
            agent_id=agent_id,
            llm_call=llm_call or self.orchestrator.llm_call,
            system_prompt=system_prompt,
            tool_executor=tool_executor or self.orchestrator.tool_executor,
        )

    def close(self) -> None:
        self.session_db.close()
