"""EvoluxAgent facade — stable entry point for orchestrator runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agent.agent_registry import AgentDefinition, AgentRegistry
from agent.context_compressor import CompressionConfig, compress_messages
from agent.memory_manager import MemoryManager
from agent.orchestrator import OrchestratorAgent
from agent.routing import FusionWeights, RoutingContext, SubAgentCandidate, fuse_routing
from agent.settings import Settings, load_settings
from agent.skill_router import SkillRouter
from agent.subagent import SubAgent
from evolux_constants import get_evolux_home
from evolux_state import SessionDB
from agent.llm import resolve_api_key
from agent.tooling import build_combined_tool_executor, get_agent_tool_definitions, get_subagent_tool_definitions
from gateway.assistant_registry import AssistantRegistry
from mcp.manager import MCPManager
from tools.orchestrator_tools import OrchestratorToolContext
from vector.embedder import create_embedder
from vector.subagent_index import SubAgentIndex


class EvoluxAgent:
    """Facade wiring SessionDB, routing, registry, orchestrator and subagents."""

    def __init__(
        self,
        llm_call: Callable[[list[dict[str, Any]]], Any],
        home: Path | None = None,
        assistant_id: str = "default",
        tool_executor: Callable[[dict[str, Any]], str] | None = None,
        settings: Settings | None = None,
    ):
        self.home = home or get_evolux_home()
        self.assistant_id = assistant_id
        self.settings = settings or load_settings(self.home)
        self.session_db = SessionDB(home=self.home)
        self.agent_registry = AgentRegistry(home=self.home)
        embedder = create_embedder(
            provider=self.settings.vector.embedding,
            api_key=resolve_api_key(self.settings.llm.provider, self.settings.llm.api_key),
        )
        vector_backend = self.settings.vector.backend
        self.skill_router = SkillRouter(self.home, embedder=embedder, backend=vector_backend)
        self.subagent_index = SubAgentIndex(
            self.home,
            registry=self.agent_registry,
            embedder=embedder,
            backend=vector_backend,
        )
        self.memory_manager = MemoryManager(home=self.home, assistant_id=assistant_id)
        self.mcp_manager = MCPManager(home=self.home, settings=self.settings)
        from mcp.registry_bridge import sync_mcp_tools

        sync_mcp_tools(self.mcp_manager)
        self.assistant_registry = AssistantRegistry(home=self.home)

        self._tool_context = OrchestratorToolContext(
            assistant_id=assistant_id,
            agent_registry=self.agent_registry,
            subagent_index=self.subagent_index,
            skill_router=self.skill_router,
            prepare_routing=self.prepare_routing,
            create_subagent_runner=self.create_subagent,
            dispatch_subagent=self.dispatch_subagent,
        )
        combined_tool_executor = tool_executor or build_combined_tool_executor(
            self._tool_context,
            assistant_id=assistant_id,
        )

        self.orchestrator = OrchestratorAgent(
            llm_call=llm_call,
            max_iterations=self.settings.orchestrator_max_iterations,
            tool_executor=combined_tool_executor,
        )

    def prepare_routing(self, user_message: str) -> RoutingContext:
        skill_candidates = self.skill_router.identify(
            user_message,
            top_k=self.settings.routing.skill_top_k,
            enable_keyword=self.settings.routing.enable_keyword,
            enable_vector=self.settings.routing.enable_vector,
        )
        raw_hits = self.subagent_index.search(
            user_message,
            assistant_id=self.assistant_id,
            top_k=self.settings.routing.subagent_top_k,
        )
        subagent_candidates: list[SubAgentCandidate] = []
        for agent_id, score, meta in raw_hits:
            registry_agent = self.agent_registry.get(agent_id)
            skills = registry_agent.skills if registry_agent else list(meta.get("skills", []))
            recency_boost = _recency_boost(registry_agent)
            subagent_candidates.append(
                SubAgentCandidate(
                    agent_id=agent_id,
                    vector_score=float(score),
                    name=meta.get("name", agent_id),
                    domain=meta.get("domain", ""),
                    skills=skills,
                    recency_boost=recency_boost,
                )
            )
        return fuse_routing(skill_candidates, subagent_candidates, self._fusion_weights())

    def _fusion_weights(self) -> FusionWeights:
        assistant = self.assistant_registry.get(self.assistant_id)
        if assistant and assistant.routing_fusion:
            return assistant.routing_fusion
        return self.settings.routing.fusion

    def _build_prefix_messages(
        self,
        routing: RoutingContext,
        *,
        include_memory: bool = True,
    ) -> list[dict[str, Any]]:
        prefix: list[dict[str, Any]] = []
        if include_memory:
            snapshot = self.memory_manager.read_snapshot()
            if snapshot:
                prefix.append({"role": "system", "content": snapshot})
        if routing.prompt_block:
            prefix.append({"role": "system", "content": routing.prompt_block})
        return prefix

    def run_orchestrator_turn(
        self,
        session_key: str,
        user_message: str,
        platform: str = "cli",
        *,
        compress: bool = True,
        tool_hook=None,
        text_hook=None,
    ):
        session_id = self.session_db.get_or_create_session(
            session_key=session_key,
            assistant_id=self.assistant_id,
            platform=platform,
        )
        history = [{"role": m["role"], "content": m["content"]} for m in self.session_db.get_messages(session_id)]

        if compress:
            compressed = compress_messages(
                history,
                CompressionConfig(keep_recent_turns=self.settings.compression.keep_recent_turns),
            )
            history = compressed.messages

        routing = self.prepare_routing(user_message)
        prefix = self._build_prefix_messages(routing)
        turn_messages = history + [{"role": "user", "content": user_message}]
        tools = get_agent_tool_definitions(platform=platform)

        result = self.orchestrator.run_turn(
            turn_messages,
            prefix_messages=prefix,
            tool_hook=tool_hook,
            text_hook=text_hook,
            tools=tools,
        )
        if result.content:
            self.session_db.append_message(session_id, "user", user_message)
            self.session_db.append_message(session_id, "assistant", result.content)
        return result

    def dispatch_subagent(
        self,
        *,
        agent_id: str,
        task: str,
        skills: list[str] | None = None,
        context_slice: str = "",
    ) -> dict[str, Any]:
        agent_def = self.agent_registry.get(agent_id)
        if agent_def is None:
            return {"error": f"unknown agent: {agent_id}"}

        skill_names = skills or agent_def.skills
        skill_instructions = self.skill_router.load_for_execution(skill_names)
        subagent_tools = get_subagent_tool_definitions(
            toolsets=agent_def.toolsets or ["evolux-code"],
            mcp_servers=list(agent_def.mcp_servers or []),
        )
        if agent_def.mcp_servers:
            for server in agent_def.mcp_servers:
                from mcp.registry_bridge import sync_mcp_tools

                sync_mcp_tools(self.mcp_manager, server)
        subagent = SubAgent(
            agent_id=agent_id,
            llm_call=self.orchestrator.llm_call,
            max_iterations=self.settings.subagent_max_iterations,
            system_prompt=agent_def.system_prompt_template,
            skill_instructions=skill_instructions,
            tool_executor=build_combined_tool_executor(
                self._tool_context,
                assistant_id=self.assistant_id,
                subagent=True,
            ),
            tool_definitions=subagent_tools,
        )
        result = subagent.run_task(task, context_slice=context_slice)
        _touch_agent_usage(self.agent_registry, agent_def)
        self.subagent_index.sync_agent(self.agent_registry.get(agent_id))
        return {
            "agent_id": agent_id,
            "content": result.content,
            "exhausted": result.exhausted,
            "skills": skill_names,
        }

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
            max_iterations=self.settings.subagent_max_iterations,
            system_prompt=system_prompt,
            tool_executor=tool_executor or self.orchestrator.tool_executor,
        )

    def close(self) -> None:
        self.mcp_manager.close()
        self.session_db.close()


def _recency_boost(agent: AgentDefinition | None) -> float:
    if agent is None:
        return 0.0
    last_used = agent.stats.get("last_used")
    if not last_used:
        return 0.0
    try:
        ts = datetime.fromisoformat(last_used)
    except ValueError:
        return 0.0
    age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
    return 1.0 if age_hours <= 24 else 0.0


def _touch_agent_usage(registry: AgentRegistry, agent: AgentDefinition) -> None:
    agent.stats["invocations"] = int(agent.stats.get("invocations", 0)) + 1
    agent.stats["last_used"] = datetime.now(timezone.utc).isoformat()
    registry.register(agent)
