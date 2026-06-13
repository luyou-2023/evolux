"""Orchestrator-only tools: dispatch, create, search, identify."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent.agent_registry import AgentDefinition
from agent.mcp_proposals import MCPProposal, MCPProposalStore
from agent.planning_state import TurnPlanningState
from agent.routing import RoutingContext, routing_decision_hints
from agent.sedimentation import build_default_system_prompt, default_toolsets_for_domain
from agent.session_monitor import is_internal_agent


@dataclass
class OrchestratorToolContext:
    assistant_id: str
    agent_registry: Any
    subagent_index: Any
    skill_router: Any
    prepare_routing: Callable[[str], Any]
    create_subagent_runner: Callable[..., Any]
    dispatch_subagent: Callable[..., Any]
    turn_planning: TurnPlanningState | None = None
    max_concurrent_subagents: int = 3
    home: Path | None = None


def _routing_defaults(
    ctx: OrchestratorToolContext,
    *,
    skills: list[str],
    domain: str,
    toolsets: list[str],
) -> tuple[list[str], list[str]]:
    resolved_skills = list(skills)
    resolved_toolsets = list(toolsets)
    routing = ctx.turn_planning.routing if ctx.turn_planning else None
    if not resolved_skills and routing:
        resolved_skills = list(routing.suggested_skills[:5])
    if not resolved_toolsets:
        resolved_toolsets = default_toolsets_for_domain(domain)
    return resolved_skills, resolved_toolsets


def handle_orchestrator_tool(name: str, arguments: dict[str, Any], ctx: OrchestratorToolContext) -> str:
    if name == "identify_skills":
        query = arguments.get("query", "")
        skills = ctx.skill_router.identify(query, top_k=5)
        return json.dumps([s.__dict__ for s in skills], ensure_ascii=False)

    if name == "search_subagents":
        query = arguments.get("query", "")
        routing = ctx.prepare_routing(query)
        payload = {
            "skill_candidates": [s.__dict__ for s in routing.skill_candidates],
            "fused_ranking": [f.__dict__ for f in routing.fused_ranking],
            "suggested_skills": routing.suggested_skills,
            "decision_hints": routing_decision_hints(routing),
            "prompt_block": routing.prompt_block,
        }
        return json.dumps(payload, ensure_ascii=False)

    if name == "list_subagents":
        agents = ctx.agent_registry.list_by_assistant(ctx.assistant_id)
        return json.dumps(
            [
                {"agent_id": a.agent_id, "name": a.name, "skills": a.skills}
                for a in agents
                if not is_internal_agent(a.agent_id) and not a.stats.get("internal")
            ],
            ensure_ascii=False,
        )

    if name == "create_subagent":
        agent_id = str(arguments.get("agent_id") or "")
        if is_internal_agent(agent_id):
            return json.dumps({"error": f"agent id reserved: {agent_id}"}, ensure_ascii=False)
        domain = str(arguments.get("domain") or "general")
        name = str(arguments.get("name") or agent_id)
        description = str(arguments.get("description") or "")
        skills, toolsets = _routing_defaults(
            ctx,
            skills=list(arguments.get("skills") or []),
            domain=domain,
            toolsets=list(arguments.get("toolsets") or []),
        )
        mcp_servers = list(arguments.get("mcp_servers") or [])
        system_prompt = str(
            arguments.get("system_prompt_template")
            or arguments.get("system_prompt")
            or ""
        ).strip()
        if not system_prompt:
            system_prompt = build_default_system_prompt(
                name=name,
                domain=domain,
                description=description,
                skills=skills,
                toolsets=toolsets,
                mcp_servers=mcp_servers,
            )
        agent = AgentDefinition(
            agent_id=agent_id,
            assistant_id=ctx.assistant_id,
            name=name,
            domain=domain,
            description=description,
            system_prompt_template=system_prompt,
            skills=skills,
            toolsets=toolsets,
            mcp_servers=mcp_servers,
        )
        ctx.agent_registry.register(agent)
        ctx.subagent_index.sync_agent(agent)
        return json.dumps(
            {
                "created": agent.agent_id,
                "skills": skills,
                "toolsets": toolsets,
                "mcp_servers": mcp_servers,
            },
            ensure_ascii=False,
        )

    if name == "dispatch_subagent":
        agent_id = str(arguments.get("agent_id") or "")
        if is_internal_agent(agent_id):
            return json.dumps({"error": f"agent reserved for system use: {agent_id}"}, ensure_ascii=False)
        if ctx.turn_planning and ctx.turn_planning.dispatch_count >= ctx.max_concurrent_subagents:
            return json.dumps(
                {
                    "error": (
                        f"max concurrent subagents reached ({ctx.max_concurrent_subagents}); "
                        "wait for current dispatches or summarize partial results"
                    )
                },
                ensure_ascii=False,
            )
        result = ctx.dispatch_subagent(
            agent_id=arguments["agent_id"],
            task=arguments.get("task", ""),
            skills=list(arguments.get("skills", [])),
            context_slice=arguments.get("context_slice", ""),
        )
        return json.dumps(result, ensure_ascii=False)

    if name == "plan_task":
        goal = str(arguments.get("goal") or "").strip()
        steps = arguments.get("steps") or []
        if not goal:
            return json.dumps({"error": "goal is required"}, ensure_ascii=False)
        if not isinstance(steps, list) or not steps:
            return json.dumps({"error": "steps array is required"}, ensure_ascii=False)
        if ctx.turn_planning is not None:
            ctx.turn_planning.plan_goal = goal
            ctx.turn_planning.plan_steps = [dict(step) for step in steps if isinstance(step, dict)]
            if ctx.home and ctx.turn_planning.session_key:
                from agent.session_plan import save_session_plan

                save_session_plan(
                    ctx.home,
                    ctx.turn_planning.session_key,
                    goal=goal,
                    steps=ctx.turn_planning.plan_steps,
                )
        return json.dumps(
            {
                "planned": True,
                "goal": goal,
                "steps": len(steps),
                "hint": "Execute steps via dispatch_subagent; update plan if scope changes.",
            },
            ensure_ascii=False,
        )

    if name == "propose_mcp_server":
        name_value = str(arguments.get("name") or "").strip()
        transport = str(arguments.get("transport") or "stdio").strip().lower()
        if not name_value:
            return json.dumps({"error": "name is required"}, ensure_ascii=False)
        if transport not in {"stdio", "http"}:
            return json.dumps({"error": "transport must be stdio or http"}, ensure_ascii=False)
        proposal = MCPProposal(
            name=name_value,
            transport=transport,
            reason=str(arguments.get("reason") or ""),
            command=arguments.get("command"),
            args=list(arguments.get("args") or []),
            url=arguments.get("url"),
        )
        if transport == "http" and not proposal.url:
            return json.dumps({"error": "url is required for http transport"}, ensure_ascii=False)
        if transport == "stdio" and not proposal.command:
            return json.dumps({"error": "command is required for stdio transport"}, ensure_ascii=False)
        store = MCPProposalStore(home=ctx.home)
        store.add_proposal(proposal)
        return json.dumps(
            {
                "proposed": name_value,
                "status": "pending",
                "approve_hint": f"User can run /mcp approve {name_value} to enable.",
            },
            ensure_ascii=False,
        )

    if name == "retire_subagent":
        agent_id = arguments.get("agent_id", "")
        agent = ctx.agent_registry.get(agent_id, include_retired=True)
        if agent is None:
            return json.dumps({"error": f"unknown agent: {agent_id}"}, ensure_ascii=False)
        ctx.agent_registry.retire(agent_id)
        retired = ctx.agent_registry.get(agent_id, include_retired=True)
        if retired:
            ctx.subagent_index.sync_agent(retired)
        return json.dumps({"retired": agent_id}, ensure_ascii=False)

    if name == "clarify":
        question = str(arguments.get("question", "")).strip()
        if not question:
            return json.dumps({"error": "question is required"}, ensure_ascii=False)
        options = arguments.get("options") or []
        if not isinstance(options, list):
            options = []
        return json.dumps(
            {
                "clarify": True,
                "question": question,
                "options": [str(item) for item in options],
            },
            ensure_ascii=False,
        )

    return json.dumps({"error": f"unknown tool: {name}"})


ORCHESTRATOR_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "identify_skills": {
        "name": "identify_skills",
        "description": "识别与查询相关的 Skill（主控自身可用 skill_view；委派时可传给子 Agent）。",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    "search_subagents": {
        "name": "search_subagents",
        "description": (
            "检索已有专家子 Agent 及融合排序；返回 decision_hints 供主控判断 "
            "dispatch 已有专家 vs create 新专家 vs 直接回答。"
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    "list_subagents": {
        "name": "list_subagents",
        "description": "列出已注册专家（子 Agent 目录）；委派前可先查看是否已有合适专家。",
        "parameters": {"type": "object", "properties": {}},
    },
    "create_subagent": {
        "name": "create_subagent",
        "description": (
            "注册新的领域专家（仅当 list/search 无合适专家且任务需重复执行或专用 toolsets/MCP 时）。"
            "一次性问答或解释请勿创建。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "name": {"type": "string"},
                "domain": {"type": "string"},
                "description": {"type": "string"},
                "system_prompt_template": {"type": "string"},
                "skills": {"type": "array", "items": {"type": "string"}},
                "toolsets": {"type": "array", "items": {"type": "string"}},
                "mcp_servers": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["agent_id"],
        },
    },
    "dispatch_subagent": {
        "name": "dispatch_subagent",
        "description": (
            "委派任务给已注册专家执行（子 Agent 类似高级工具）。"
            "主控负责理解需求与汇总；专家返回结构化结果。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "task": {"type": "string"},
                "skills": {"type": "array", "items": {"type": "string"}},
                "context_slice": {"type": "string"},
            },
            "required": ["agent_id", "task"],
        },
    },
    "plan_task": {
        "name": "plan_task",
        "description": (
            "Create a structured multi-step plan before delegating work to subagents."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "agent_id": {"type": "string"},
                            "skills": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["action"],
                    },
                },
            },
            "required": ["goal", "steps"],
        },
    },
    "propose_mcp_server": {
        "name": "propose_mcp_server",
        "description": (
            "Propose a new MCP server for user approval (/mcp approve). Does not enable until approved."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "transport": {"type": "string", "enum": ["stdio", "http"]},
                "command": {"type": "string"},
                "args": {"type": "array", "items": {"type": "string"}},
                "url": {"type": "string"},
                "reason": {"type": "string"},
            },
            "required": ["name", "transport"],
        },
    },
    "retire_subagent": {
        "name": "retire_subagent",
        "description": "Retire a subagent and remove it from vector search.",
        "parameters": {
            "type": "object",
            "properties": {"agent_id": {"type": "string"}},
            "required": ["agent_id"],
        },
    },
    "clarify": {
        "name": "clarify",
        "description": "Ask the user a clarifying question when requirements are underspecified.",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "options": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["question"],
        },
    },
}


def get_orchestrator_schemas() -> list[dict[str, Any]]:
    return [{"type": "function", "function": schema} for schema in ORCHESTRATOR_TOOL_SCHEMAS.values()]


def build_tool_executor(ctx: OrchestratorToolContext) -> Callable[[dict[str, Any]], str]:
    def _executor(tool_call: dict[str, Any]) -> str:
        name = tool_call.get("name", "")
        arguments = tool_call.get("arguments", {})
        if isinstance(arguments, str):
            arguments = json.loads(arguments) if arguments else {}
        return handle_orchestrator_tool(name, arguments, ctx)

    return _executor
