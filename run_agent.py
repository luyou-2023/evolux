"""EvoluxAgent facade — stable entry point for orchestrator runtime."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agent.agent_registry import AgentDefinition, AgentRegistry
from agent.context_compressor import CompressionConfig, compress_messages
from agent.conversation_loop import ConversationResult
from agent.slash_commands import SlashCommandContext, try_handle_slash_command
from agent.memory_manager import MemoryManager
from agent.expert_promotion import maybe_promote_expert, record_task_observation
from agent.goals_manager import GoalsManager
from agent.memory_sedimentation import extract_memory_entries_llm, sediment_global_memory
from agent.orchestrator import OrchestratorAgent
from agent.orchestrator_prompt import build_orchestrator_system_prompt
from agent.planning_state import TurnPlanningState
from agent.session_plan import load_session_plan, save_session_plan
from agent.routing import FusionWeights, RoutingContext, SubAgentCandidate, fuse_routing
from agent.sedimentation import sediment_agent_task, sediment_turn_solution
from agent.settings import Settings, load_settings
from agent.session_monitor import (
    SESSION_MONITOR_AGENT_ID,
    SessionMonitorHook,
    ensure_session_monitor_agent,
    is_internal_agent,
    turn_end_message,
    turn_start_message,
)
from agent.skill_router import SkillRouter
from agent.subagent import SubAgent
from evolux_constants import get_evolux_home
from evolux_state import SessionDB
from agent.activity_hooks import ActivityToolHook, CombinedToolHook
from agent.llm import resolve_api_key
from agent.tool_selection import select_tools_for_turn
from agent.trace_hooks import TraceToolHook
from agent.turn_cancel import bind_session_key, clear_turn_cancel, unbind_session_key
from agent.turn_trace import TurnTrace
from agent.tooling import build_combined_tool_executor, get_agent_tool_definitions, get_subagent_tool_definitions
from gateway.activity import emit_activity
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
        self.goals_manager = GoalsManager(home=self.home, assistant_id=assistant_id)
        self.mcp_manager = MCPManager(home=self.home, settings=self.settings, llm_call=llm_call)
        from mcp.registry_bridge import sync_mcp_tools

        sync_mcp_tools(self.mcp_manager)
        self.assistant_registry = AssistantRegistry(home=self.home)
        ensure_session_monitor_agent(self.agent_registry, assistant_id)

        self._turn_planning = TurnPlanningState()
        self._tool_context = OrchestratorToolContext(
            assistant_id=assistant_id,
            agent_registry=self.agent_registry,
            subagent_index=self.subagent_index,
            skill_router=self.skill_router,
            prepare_routing=self.prepare_routing,
            create_subagent_runner=self.create_subagent,
            dispatch_subagent=self.dispatch_subagent,
            turn_planning=self._turn_planning,
            max_concurrent_subagents=self.settings.orchestrator_max_concurrent_subagents,
            home=self.home,
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
        self._turn_trace = None
        self._progress_callback = None
        self._session_key = ""
        self._platform = "cli"

    def _approve_mcp_server(self, name: str, config: dict[str, Any]) -> None:
        self.settings.mcp.servers[name] = dict(config)
        self.mcp_manager.register_server(name, config)
        from mcp.registry_bridge import sync_mcp_tools

        sync_mcp_tools(self.mcp_manager, name)

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
        session_key: str = "",
    ) -> list[dict[str, Any]]:
        prefix: list[dict[str, Any]] = []
        prefix.append(
            {
                "role": "system",
                "content": build_orchestrator_system_prompt(
                    max_concurrent_subagents=self.settings.orchestrator_max_concurrent_subagents,
                ),
            }
        )
        if include_memory:
            snapshot = self.memory_manager.read_snapshot()
            solutions = self.memory_manager.read_solutions_snapshot()
            goals = self.goals_manager.read_snapshot()
            plan = load_session_plan(self.home, session_key) if session_key else ""
            memory_parts = []
            if snapshot:
                memory_parts.append(snapshot)
            if goals:
                memory_parts.append(goals)
            if solutions:
                memory_parts.append(f"<!-- SOLUTIONS -->\n{solutions}")
            if plan:
                memory_parts.append(plan)
            if memory_parts:
                prefix.append({"role": "system", "content": "\n\n".join(memory_parts)})
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
        trace: TurnTrace | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ):
        self._turn_trace = trace
        self._progress_callback = progress_callback if self.settings.monitor.push_interim else None
        self._session_key = session_key
        self._platform = platform
        clear_turn_cancel(session_key)
        cancel_token = bind_session_key(session_key)
        try:
            return self._run_orchestrator_turn_body(
                session_key=session_key,
                user_message=user_message,
                platform=platform,
                compress=compress,
                tool_hook=tool_hook,
                text_hook=text_hook,
                trace=trace,
            )
        finally:
            unbind_session_key(cancel_token)
            self._turn_trace = None
            self._progress_callback = None

    def _run_orchestrator_turn_body(
        self,
        session_key: str,
        user_message: str,
        platform: str,
        *,
        compress: bool,
        tool_hook,
        text_hook,
        trace: TurnTrace | None,
    ):
        session_id = self.session_db.get_or_create_session(
            session_key=session_key,
            assistant_id=self.assistant_id,
            platform=platform,
        )
        slash = try_handle_slash_command(
            user_message,
            ctx=SlashCommandContext(
                session_key=session_key,
                assistant_id=self.assistant_id,
                platform=platform,
                session_db=self.session_db,
                on_progress=self._progress_callback,
                settings=self.settings,
                home=self.home,
                goals_manager=self.goals_manager,
                on_mcp_approved=self._approve_mcp_server,
            ),
        )
        if slash and slash.handled:
            emit_activity(
                "slash_command",
                session_key=session_key,
                assistant_id=self.assistant_id,
                platform=platform,
                tool=SESSION_MONITOR_AGENT_ID,
                detail=user_message[:200],
            )
            if slash.rerun_message is None:
                return ConversationResult(
                    content=slash.reply,
                    messages=[],
                    iterations_used=0,
                    plain_reply=slash.plain_reply,
                    interactive_card=slash.interactive_card,
                    switch_session_key=slash.switch_session_key,
                )
            user_message = slash.rerun_message

        history = [
            {"role": m["role"], "content": m["content"]}
            for m in self.session_db.load_history(session_key)
        ]

        if compress:
            compressed = compress_messages(
                history,
                CompressionConfig(keep_recent_turns=self.settings.compression.keep_recent_turns),
            )
            history = compressed.messages

        routing = self.prepare_routing(user_message)
        record_task_observation(
            self.home,
            assistant_id=self.assistant_id,
            user_message=user_message,
        )
        promotion_prompt, _created = maybe_promote_expert(
            self.home,
            assistant_id=self.assistant_id,
            user_message=user_message,
            routing=routing,
            agent_registry=self.agent_registry,
            subagent_index=self.subagent_index,
            settings=self.settings.expert_promotion,
        )
        if promotion_prompt:
            routing.prompt_block = f"{routing.prompt_block}\n\n{promotion_prompt}".strip()
        if _created:
            routing = self.prepare_routing(user_message)
            if promotion_prompt:
                routing.prompt_block = f"{routing.prompt_block}\n\n{promotion_prompt}".strip()

        self._turn_planning.reset(user_message=user_message, session_key=session_key)
        self._turn_planning.routing = routing
        prefix = self._build_prefix_messages(routing, session_key=session_key)
        turn_messages = history + [{"role": "user", "content": user_message}]
        tools = get_agent_tool_definitions(platform=platform)
        if self.settings.routing.trim_tools:
            tools = select_tools_for_turn(
                tools,
                routing,
                platform=platform,
                max_tools=self.settings.routing.tool_max,
            )

        activity_hook = ActivityToolHook(
            session_key=session_key,
            assistant_id=self.assistant_id,
            platform=platform,
        )
        hooks = [activity_hook]
        monitor_hook: SessionMonitorHook | None = None
        if self.settings.monitor.enabled:
            monitor_hook = SessionMonitorHook(
                session_key=session_key,
                assistant_id=self.assistant_id,
                platform=platform,
                on_progress=self._progress_callback,
            )
            hooks.append(monitor_hook)
        if trace is not None:
            trace.user_message = user_message[:200]
            trace.set_routing(
                skills=[item.skill_name for item in routing.skill_candidates[:5]],
                agents=[item.agent_id for item in routing.fused_ranking[:5]],
            )
            hooks.append(TraceToolHook(trace))
        if tool_hook is not None:
            hooks.append(tool_hook)
        merged_tool_hook = CombinedToolHook(*hooks) if len(hooks) > 1 else hooks[0]

        emit_activity(
            "turn_start",
            session_key=session_key,
            assistant_id=self.assistant_id,
            platform=platform,
            detail=user_message[:200],
        )
        if monitor_hook is not None:
            monitor_hook.push(turn_start_message(user_message))
        result = self.orchestrator.run_turn(
            turn_messages,
            prefix_messages=prefix,
            tool_hook=merged_tool_hook,
            text_hook=text_hook,
            tools=tools,
            tool_choice=self.settings.llm.tool_choice,
        )
        emit_activity(
            "turn_end",
            session_key=session_key,
            assistant_id=self.assistant_id,
            platform=platform,
            detail=(result.content or "")[:200],
        )
        if monitor_hook is not None:
            end_msg = turn_end_message(subagent_count=monitor_hook.subagent_dispatches)
            if end_msg:
                monitor_hook.push(end_msg)
        if result.content:
            self.session_db.append_message(session_id, "user", user_message)
            self.session_db.append_message(session_id, "assistant", result.content)
        if (
            self.settings.sedimentation.enabled
            and result.content
            and self._turn_planning.dispatches
        ):
            sediment_turn_solution(
                self.memory_manager,
                user_message=user_message,
                final_reply=result.content,
                dispatches=self._turn_planning.dispatches,
            )
        if (
            self.settings.sedimentation.enabled
            and self.settings.sedimentation.memory_after_turn
            and result.content
        ):
            extract_fn = None
            if self.settings.sedimentation.llm_extract:
                extract_fn = lambda u, r, d: extract_memory_entries_llm(
                    self.orchestrator.llm_call, u, r, d
                )
            sediment_global_memory(
                self.memory_manager,
                user_message=user_message,
                final_reply=result.content,
                dispatches=self._turn_planning.dispatches,
                extract_fn=extract_fn,
            )
        for dispatch in self._turn_planning.dispatches:
            record_task_observation(
                self.home,
                assistant_id=self.assistant_id,
                user_message=user_message,
                increment=False,
                agent_id=dispatch["agent_id"],
                skills=list(dispatch.get("skills") or []),
            )
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
        if is_internal_agent(agent_id):
            return {"error": f"agent reserved for system use: {agent_id}"}
        if self._turn_planning.dispatch_count >= self.settings.orchestrator_max_concurrent_subagents:
            return {
                "error": (
                    f"max concurrent subagents reached "
                    f"({self.settings.orchestrator_max_concurrent_subagents})"
                )
            }

        skill_names = skills or agent_def.skills
        skill_instructions = self.skill_router.load_for_execution(skill_names)
        system_prompt = agent_def.system_prompt_template
        agent_memory = self.memory_manager.read_agent_memory(agent_id)
        if agent_memory:
            memory_block = f"## 领域记忆（历史任务沉淀）\n{agent_memory}"
            system_prompt = f"{system_prompt}\n\n{memory_block}".strip() if system_prompt else memory_block
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
            system_prompt=system_prompt,
            skill_instructions=skill_instructions,
            tool_executor=build_combined_tool_executor(
                self._tool_context,
                assistant_id=self.assistant_id,
                subagent=True,
            ),
            tool_definitions=subagent_tools,
        )
        subagent_hooks = []
        if self._turn_trace is not None:
            subagent_hooks.append(TraceToolHook(self._turn_trace, agent_id=agent_id))
        if self.settings.monitor.enabled and self._progress_callback is not None:
            subagent_hooks.append(
                SessionMonitorHook(
                    session_key=self._session_key,
                    assistant_id=self.assistant_id,
                    platform=self._platform,
                    on_progress=self._progress_callback,
                    nested_agent_id=agent_id,
                )
            )
        subagent_hook = CombinedToolHook(*subagent_hooks) if subagent_hooks else None
        result = subagent.run_task(task, context_slice=context_slice, tool_hook=subagent_hook)
        _touch_agent_usage(self.agent_registry, agent_def)
        self.subagent_index.sync_agent(self.agent_registry.get(agent_id))
        if self.settings.sedimentation.enabled and result.content:
            sediment_agent_task(
                self.memory_manager,
                agent_id=agent_id,
                task=task,
                summary=str(result.content),
                skills=skill_names,
            )
        self._turn_planning.record_dispatch(
            agent_id=agent_id,
            task=task,
            skills=skill_names,
            summary=str(result.content or ""),
            exhausted=result.exhausted,
        )
        payload = {
            "agent_id": agent_id,
            "content": result.content,
            "exhausted": result.exhausted,
            "skills": skill_names,
        }
        if self._turn_trace is not None:
            self._turn_trace.add_subagent(
                agent_id=agent_id,
                task=task,
                summary=str(result.content or ""),
                status="error" if result.exhausted else "ok",
            )
        return payload

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
