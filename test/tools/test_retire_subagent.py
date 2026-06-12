import json

from agent.agent_registry import AgentDefinition, AgentRegistry
from agent.routing import fuse_routing
from agent.skill_router import SkillRouter
from tools.orchestrator_tools import OrchestratorToolContext, handle_orchestrator_tool
from vector.subagent_index import SubAgentIndex


def test_retire_subagent_tool(evolux_home):
    registry = AgentRegistry(home=evolux_home)
    index = SubAgentIndex(evolux_home, registry=registry)
    agent = AgentDefinition(
        agent_id="temp-expert",
        assistant_id="default",
        name="Temp",
        domain="general",
        description="temporary",
    )
    registry.register(agent)
    index.sync_agent(agent)

    ctx = OrchestratorToolContext(
        assistant_id="default",
        agent_registry=registry,
        subagent_index=index,
        skill_router=SkillRouter(evolux_home),
        prepare_routing=lambda q: fuse_routing([], []),
        create_subagent_runner=lambda **_: {},
        dispatch_subagent=lambda **_: {"content": "ok"},
    )
    out = handle_orchestrator_tool("retire_subagent", {"agent_id": "temp-expert"}, ctx)
    payload = json.loads(out)
    assert payload["retired"] == "temp-expert"
    assert registry.get("temp-expert") is None
    assert "temp-expert" not in index.store._read()
