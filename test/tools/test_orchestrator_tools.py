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
