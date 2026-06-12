"""Minimal Evolux ACP stdio server."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import acp
from acp.interfaces import Client
from acp.schema import (
    AgentCapabilities,
    CloseSessionResponse,
    ForkSessionResponse,
    Implementation,
    InitializeResponse,
    ListSessionsResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptCapabilities,
    PromptResponse,
    ResumeSessionResponse,
    SessionCapabilities,
    SessionInfo,
    SetSessionConfigOptionResponse,
    SetSessionModeResponse,
    SetSessionModelResponse,
    TextContentBlock,
)

from acp_adapter.session import AcpSessionManager

logger = logging.getLogger("evolux.acp")
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="evolux-acp")


class EvoluxACPAgent:
    def __init__(self) -> None:
        self.session_manager = AcpSessionManager()
        self._conn = None

    async def on_connect(self, conn: Client) -> None:
        self._conn = conn

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: Any | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        return InitializeResponse(
            protocol_version=acp.PROTOCOL_VERSION,
            agent_info=Implementation(name="evolux", version="0.4.0"),
            agent_capabilities=AgentCapabilities(
                load_session=False,
                prompt_capabilities=PromptCapabilities(image=False),
                session_capabilities=SessionCapabilities(),
            ),
            auth_methods=[],
        )

    async def authenticate(self, method_id: str, **kwargs: Any) -> Any:
        return None

    async def new_session(self, cwd: str, mcp_servers: list | None = None, **kwargs: Any) -> NewSessionResponse:
        state = self.session_manager.create_session(cwd=cwd)
        return NewSessionResponse(session_id=state.session_id)

    async def load_session(
        self, cwd: str, session_id: str, mcp_servers: list | None = None, **kwargs: Any
    ) -> LoadSessionResponse | None:
        if self.session_manager.get_session(session_id):
            return LoadSessionResponse()
        return None

    async def list_sessions(self, cursor: str | None = None, cwd: str | None = None, **kwargs: Any) -> ListSessionsResponse:
        sessions = [
            SessionInfo(session_id=sid, cwd=state.cwd, title=f"Evolux {sid[:8]}")
            for sid, state in self.session_manager._sessions.items()
        ]
        return ListSessionsResponse(sessions=sessions)

    async def set_session_mode(self, mode_id: str, session_id: str, **kwargs: Any) -> SetSessionModeResponse | None:
        return SetSessionModeResponse()

    async def set_session_model(self, model_id: str, session_id: str, **kwargs: Any) -> SetSessionModelResponse | None:
        return SetSessionModelResponse()

    async def set_config_option(
        self, config_id: str, session_id: str, value: str | bool, **kwargs: Any
    ) -> SetSessionConfigOptionResponse | None:
        return SetSessionConfigOptionResponse()

    async def prompt(
        self,
        prompt: list[TextContentBlock],
        session_id: str,
        message_id: str | None = None,
        **kwargs: Any,
    ) -> PromptResponse:
        state = self.session_manager.get_session(session_id)
        if state is None:
            return PromptResponse(stop_reason="refusal")

        user_text = "\n".join(block.text for block in prompt if isinstance(block, TextContentBlock)).strip()
        if not user_text:
            return PromptResponse(stop_reason="end_turn")

        loop = asyncio.get_running_loop()
        hook = None
        if self._conn:
            from acp_adapter.progress import AcpToolProgressHook

            hook = AcpToolProgressHook(loop=loop, conn=self._conn, session_id=session_id)

        def _run_turn() -> str:
            result = state.agent.run_orchestrator_turn(
                state.session_key,
                user_text,
                platform="acp",
                tool_hook=hook,
            )
            return result.content or ""

        content = await loop.run_in_executor(_executor, _run_turn)
        if self._conn and content:
            update = acp.update_agent_message_text(content)
            await self._conn.session_update(session_id, update)
        return PromptResponse(stop_reason="end_turn")

    async def fork_session(
        self, cwd: str, session_id: str, mcp_servers: list | None = None, **kwargs: Any
    ) -> ForkSessionResponse:
        state = self.session_manager.create_session(cwd=cwd)
        return ForkSessionResponse(session_id=state.session_id)

    async def resume_session(
        self, cwd: str, session_id: str, mcp_servers: list | None = None, **kwargs: Any
    ) -> ResumeSessionResponse:
        if not self.session_manager.get_session(session_id):
            state = self.session_manager.create_session(cwd=cwd)
            session_id = state.session_id
        return ResumeSessionResponse(session_id=session_id)

    async def close_session(self, session_id: str, **kwargs: Any) -> CloseSessionResponse | None:
        self.session_manager.close_session(session_id)
        return CloseSessionResponse()

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        return None

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {"error": f"unsupported ext method: {method}"}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        return None
