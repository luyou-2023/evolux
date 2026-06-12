"""Orchestrator-only tools: dispatch, create, search, identify."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from agent.agent_registry import AgentDefinition
from agent.routing import SubAgentCandidate


@dataclass
class OrchestratorToolContext:
    assistant_id: str
    agent_registry: Any
    subagent_index: Any
    skill_router: Any
    prepare_routing: Callable[[str], Any]
    create_subagent_runner: Callable[..., Any]
    dispatch_subagent: Callable[..., Any]


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
            "prompt_block": routing.prompt_block,
        }
        return json.dumps(payload, ensure_ascii=False)

    if name == "list_subagents":
        agents = ctx.agent_registry.list_by_assistant(ctx.assistant_id)
        return json.dumps(
            [{"agent_id": a.agent_id, "name": a.name, "skills": a.skills} for a in agents],
            ensure_ascii=False,
        )

    if name == "create_subagent":
        agent = AgentDefinition(
            agent_id=arguments["agent_id"],
            assistant_id=ctx.assistant_id,
            name=arguments.get("name", arguments["agent_id"]),
            domain=arguments.get("domain", "general"),
            description=arguments.get("description", ""),
            skills=list(arguments.get("skills", [])),
            toolsets=list(arguments.get("toolsets", [])),
        )
        ctx.agent_registry.register(agent)
        ctx.subagent_index.sync_agent(agent)
        return json.dumps({"created": agent.agent_id}, ensure_ascii=False)

    if name == "dispatch_subagent":
        result = ctx.dispatch_subagent(
            agent_id=arguments["agent_id"],
            task=arguments.get("task", ""),
            skills=list(arguments.get("skills", [])),
            context_slice=arguments.get("context_slice", ""),
        )
        return json.dumps(result, ensure_ascii=False)

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

    return json.dumps({"error": f"unknown tool: {name}"})


ORCHESTRATOR_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "identify_skills": {
        "name": "identify_skills",
        "description": "Identify relevant skills for a query (triple-route preflight).",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    "search_subagents": {
        "name": "search_subagents",
        "description": "Search subagents with fused routing context.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    "list_subagents": {
        "name": "list_subagents",
        "description": "List registered subagents for the current assistant.",
        "parameters": {"type": "object", "properties": {}},
    },
    "create_subagent": {
        "name": "create_subagent",
        "description": "Register a new domain subagent.",
        "parameters": {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string"},
                "name": {"type": "string"},
                "domain": {"type": "string"},
                "description": {"type": "string"},
                "skills": {"type": "array", "items": {"type": "string"}},
                "toolsets": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["agent_id"],
        },
    },
    "dispatch_subagent": {
        "name": "dispatch_subagent",
        "description": "Delegate a task to a registered subagent.",
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
    "retire_subagent": {
        "name": "retire_subagent",
        "description": "Retire a subagent and remove it from vector search.",
        "parameters": {
            "type": "object",
            "properties": {"agent_id": {"type": "string"}},
            "required": ["agent_id"],
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
