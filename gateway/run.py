"""Async gateway runner bridging platform events to EvoluxAgent."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from gateway.activity import emit_activity
from gateway.assistant_registry import AssistantRegistry
from gateway.events import MessageEvent
from agent.turn_trace import TurnTrace
from gateway.platforms.feishu_format import (
    build_feishu_clarify_card,
    build_feishu_post_content,
    find_clarify_request,
)
from gateway.platforms.feishu_api import FeishuAPIClient, build_feishu_client
from gateway.session import build_session_key
from run_agent import EvoluxAgent

logger = logging.getLogger("evolux.gateway")


@dataclass
class GatewayResponse:
    session_key: str
    assistant_id: str
    content: str | None
    exhausted: bool = False
    reply_sent: bool = False
    reply_error: str | None = None
    trace: TurnTrace | None = None


class GatewayRunner:
    """Route inbound platform messages to orchestrator turns."""

    def __init__(
        self,
        home: Path,
        llm_call: Callable[[list[dict[str, Any]]], Any],
        *,
        max_workers: int = 4,
        send_feishu_reply: bool = True,
    ):
        self.home = home
        self.llm_call = llm_call
        self.send_feishu_reply = send_feishu_reply
        self.assistant_registry = AssistantRegistry(home=home)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="evolux-agent")
        self._agents: dict[str, EvoluxAgent] = {}
        self._feishu_clients: dict[str, FeishuAPIClient] = {}

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
        if event.is_card_action:
            emit_activity(
                "card_action_received",
                session_key=session_key,
                assistant_id=event.assistant_id,
                platform=event.source.platform,
                detail=event.card_action_option or event.text[:200],
            )
        else:
            emit_activity(
                "message_received",
                session_key=session_key,
                assistant_id=event.assistant_id,
                platform=event.source.platform,
                detail=event.text[:200],
            )
        agent = self._get_agent(event.assistant_id)
        trace = TurnTrace()
        result = agent.run_orchestrator_turn(
            session_key=session_key,
            user_message=event.text,
            platform=event.source.platform,
            trace=trace,
        )
        response = GatewayResponse(
            session_key=session_key,
            assistant_id=event.assistant_id,
            content=result.content,
            exhausted=result.exhausted,
            trace=trace,
        )
        if (
            self.send_feishu_reply
            and event.source.platform == "feishu"
            and response.content
            and event.source.chat_id
        ):
            self._try_send_feishu_reply(event, response)
        return response

    def _try_send_feishu_reply(self, event: MessageEvent, response: GatewayResponse) -> None:
        client = self._get_feishu_client(event.assistant_id)
        if not client:
            return
        try:
            clarify = find_clarify_request(response.trace)
            if clarify:
                client.send_interactive(event.source.chat_id, build_feishu_clarify_card(clarify))
            post = build_feishu_post_content(answer=response.content or "", trace=response.trace)
            client.send_post(event.source.chat_id, post)
            response.reply_sent = True
        except Exception as exc:
            response.reply_error = str(exc)
            logger.warning("Feishu reply failed assistant=%s: %s", event.assistant_id, exc)
            try:
                client.send_text(event.source.chat_id, response.content or "")
                response.reply_sent = True
                response.reply_error = None
            except Exception as fallback_exc:
                response.reply_error = str(fallback_exc)

    def _get_feishu_client(self, assistant_id: str) -> FeishuAPIClient | None:
        if assistant_id in self._feishu_clients:
            return self._feishu_clients[assistant_id]

        assistant = self.assistant_registry.get(assistant_id)
        if not assistant:
            return None
        platform_cfg = assistant.platforms.get("feishu") or {}
        client = build_feishu_client(platform_cfg)
        if client:
            self._feishu_clients[assistant_id] = client
        return client

    async def handle_message(self, event: MessageEvent) -> GatewayResponse:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self.handle_message_sync, event)

    def shutdown(self) -> None:
        for agent in self._agents.values():
            agent.close()
        self._agents.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)
