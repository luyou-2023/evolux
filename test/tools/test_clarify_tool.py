import json

from model_tools import filter_subagent_tools, get_tool_definitions
from tools.discover import ensure_tools_loaded
from tools.orchestrator_tools import OrchestratorToolContext, handle_orchestrator_tool
from agent.agent_registry import AgentRegistry
from agent.routing import fuse_routing
from agent.skill_router import SkillRouter
from vector.subagent_index import SubAgentIndex


def test_clarify_tool_returns_structured_question(evolux_home):
    ctx = OrchestratorToolContext(
        assistant_id="default",
        agent_registry=AgentRegistry(home=evolux_home),
        subagent_index=SubAgentIndex(evolux_home),
        skill_router=SkillRouter(evolux_home),
        prepare_routing=lambda q: fuse_routing([], []),
        create_subagent_runner=lambda **_: {},
        dispatch_subagent=lambda **_: {"content": "ok"},
    )
    out = handle_orchestrator_tool(
        "clarify",
        {"question": "Which repo?", "options": ["evolux", "hermes"]},
        ctx,
    )
    payload = json.loads(out)
    assert payload["clarify"] is True
    assert payload["question"] == "Which repo?"
    assert payload["options"] == ["evolux", "hermes"]


def test_clarify_exposed_to_orchestrator_not_subagent():
    ensure_tools_loaded()
    orchestrator_names = {
        item["function"]["name"]
        for item in get_tool_definitions(platform="cli")
        if item.get("function")
    }
    subagent_names = filter_subagent_tools(orchestrator_names)
    assert "clarify" in orchestrator_names
    assert "clarify" not in subagent_names
