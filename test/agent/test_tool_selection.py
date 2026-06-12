from agent.routing import RoutingContext, SkillCandidate
from agent.tool_selection import ORCHESTRATOR_ALWAYS, select_tools_for_turn
from model_tools import get_tool_definitions
from tools.discover import ensure_tools_loaded


def test_trimmed_tools_always_include_orchestrator_core():
    ensure_tools_loaded()
    routing = RoutingContext([], [], [], [])
    trimmed = select_tools_for_turn(
        get_tool_definitions(platform="cli", include_mcp=False),
        routing,
        platform="cli",
        include_mcp=False,
    )
    names = {item["function"]["name"] for item in trimmed}
    assert ORCHESTRATOR_ALWAYS.issubset(names)


def test_feishu_skill_adds_doc_tools():
    ensure_tools_loaded()
    routing = RoutingContext(
        skill_candidates=[SkillCandidate("feishu-doc", 0.8)],
        subagent_candidates=[],
        fused_ranking=[],
        suggested_skills=["feishu-doc"],
    )
    trimmed = select_tools_for_turn(
        get_tool_definitions(platform="feishu", include_mcp=False),
        routing,
        platform="feishu",
        include_mcp=False,
    )
    names = {item["function"]["name"] for item in trimmed}
    assert "feishu_doc_read" in names
