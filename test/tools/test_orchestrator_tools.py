import json

from agent.agent_registry import AgentDefinition, AgentRegistry
from agent.routing import fuse_routing
from agent.skill_router import SkillRouter
from tools.orchestrator_tools import OrchestratorToolContext, handle_orchestrator_tool
from vector.subagent_index import SubAgentIndex


def test_create_subagent_tool_registers_agent(evolux_home):
    registry = AgentRegistry(home=evolux_home)
    index = SubAgentIndex(evolux_home, registry=registry)
    router = SkillRouter(evolux_home)

    ctx = OrchestratorToolContext(
        assistant_id="default",
        agent_registry=registry,
        subagent_index=index,
        skill_router=router,
        prepare_routing=lambda q: fuse_routing([], []),
        create_subagent_runner=lambda **_: {},
        dispatch_subagent=lambda **_: {"content": "ok"},
    )
    out = handle_orchestrator_tool(
        "create_subagent",
        {
            "agent_id": "code-expert",
            "name": "Code Expert",
            "domain": "code",
            "description": "Python",
            "skills": ["git"],
        },
        ctx,
    )
    payload = json.loads(out)
    assert payload["created"] == "code-expert"
    assert registry.get("code-expert") is not None


def test_list_subagents_hides_internal_monitor(evolux_home):
    registry = AgentRegistry(home=evolux_home)
    registry.register(
        AgentDefinition(
            agent_id="_session-monitor",
            assistant_id="default",
            name="Session Monitor",
            domain="orchestration",
            description="internal",
            stats={"internal": True},
        )
    )
    registry.register(
        AgentDefinition(
            agent_id="writer",
            assistant_id="default",
            name="Writer",
            domain="writing",
            description="writes",
        )
    )
    ctx = OrchestratorToolContext(
        assistant_id="default",
        agent_registry=registry,
        subagent_index=SubAgentIndex(evolux_home, registry=registry),
        skill_router=SkillRouter(evolux_home),
        prepare_routing=lambda q: fuse_routing([], []),
        create_subagent_runner=lambda **_: {},
        dispatch_subagent=lambda **_: {"content": "ok"},
    )
    out = json.loads(handle_orchestrator_tool("list_subagents", {}, ctx))
    ids = {item["agent_id"] for item in out}
    assert "writer" in ids
    assert "_session-monitor" not in ids


def test_dispatch_subagent_blocks_internal_agent(evolux_home):
    ctx = OrchestratorToolContext(
        assistant_id="default",
        agent_registry=AgentRegistry(home=evolux_home),
        subagent_index=SubAgentIndex(evolux_home),
        skill_router=SkillRouter(evolux_home),
        prepare_routing=lambda q: fuse_routing([], []),
        create_subagent_runner=lambda **_: {},
        dispatch_subagent=lambda **_: {"content": "ok"},
    )
    out = json.loads(
        handle_orchestrator_tool(
            "dispatch_subagent",
            {"agent_id": "_session-monitor", "task": "watch"},
            ctx,
        )
    )
    assert "error" in out
