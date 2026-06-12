"""Async gateway runner bridging platform events to EvoluxAgent."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from gateway.assistant_registry import AssistantRegistry
from gateway.events import MessageEvent
from gateway.session import build_session_key
from run_agent import EvoluxAgent


@dataclass
class GatewayResponse:
    session_key: str
    assistant_id: str
    content: str | None
    exhausted: bool = False


class GatewayRunner:
    """Route inbound platform messages to orchestrator turns."""

    def __init__(
        self,
        home: Path,
        llm_call: Callable[[list[dict[str, Any]]], Any],
        *,
        max_workers: int = 4,
    ):
        self.home = home
        self.llm_call = llm_call
        self.assistant_registry = AssistantRegistry(home=home)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="evolux-agent")
        self._agents: dict[str, EvoluxAgent] = {}

    def _get_agent(self, assistant_id: str) -> EvoluxAgent:
        if assistant_id not in self._agents:
            self._agents[assistant_id] = EvoluxAgent(
                llm_call=self.llm_call,
                home=self.home,
                assistant_id=assistant_id,
            )
        return self._agents[assistant_id]

    def handle_message_sync(self, event: MessageEvent) -> GatewayResponse:
        session_key = build_session_key(event.assistant_id, event.source)
        agent = self._get_agent(event.assistant_id)
        result = agent.run_orchestrator_turn(
            session_key=session_key,
            user_message=event.text,
            platform=event.source.platform,
        )
        return GatewayResponse(
            session_key=session_key,
            assistant_id=event.assistant_id,
            content=result.content,
            exhausted=result.exhausted,
        )

    async def handle_message(self, event: MessageEvent) -> GatewayResponse:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self.handle_message_sync, event)

    def shutdown(self) -> None:
        for agent in self._agents.values():
            agent.close()
        self._agents.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)
