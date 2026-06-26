"""Register bundled domain experts (ui-automation, etc.)."""

from __future__ import annotations

from agent.agent_registry import AgentDefinition, AgentRegistry
from agent.sedimentation import build_default_system_prompt
from vector.subagent_index import SubAgentIndex

UI_AUTOMATION_EXPERT = AgentDefinition(
    agent_id="ui-automation-expert",
    assistant_id="",  # filled on install
    name="UI Automation Expert",
    domain="ui-test",
    description=(
        "Vision-driven UI/E2E testing via midscenejs_luke + Playwright. "
        "Uses aiAct/aiQuery/aiAssert instead of brittle selectors."
    ),
    system_prompt_template="",  # built on install
    skills=["midscene-ui", "plan"],
    toolsets=["evolux-ui-test"],
    mcp_servers=[],
    stats={"bundled": True},
)


def build_ui_automation_prompt() -> str:
    return build_default_system_prompt(
        name="UI Automation Expert",
        domain="ui-test",
        description=(
            "Execute web UI tests with midscenejs_luke (Luke's vision-driven engine) and Playwright. "
            "Prefer midscene_luke_run or midscene_luke_run_playwright_test over raw terminal."
        ),
        skills=["midscene-ui", "plan"],
        toolsets=["evolux-ui-test"],
        mcp_servers=[],
    ) + (
        "\n\n## 执行规范\n"
        "- UI 操作/断言：必须用 midscene_luke_* 工具\n"
        "- 步骤：goto → act/tap/input → wait → query → assert\n"
        "- 失败时返回 error 与已执行 steps\n"
        "- 可 midscene_luke_init_project 初始化 ~/.evolux/ui-tests 后维护 spec"
    )


def install_ui_automation_expert(
    registry: AgentRegistry,
    subagent_index: SubAgentIndex,
    *,
    assistant_id: str,
    replace: bool = False,
) -> AgentDefinition:
    existing = registry.get("ui-automation-expert")
    if existing and not replace:
        return existing

    agent = AgentDefinition(
        agent_id=UI_AUTOMATION_EXPERT.agent_id,
        assistant_id=assistant_id,
        name=UI_AUTOMATION_EXPERT.name,
        domain=UI_AUTOMATION_EXPERT.domain,
        description=UI_AUTOMATION_EXPERT.description,
        system_prompt_template=build_ui_automation_prompt(),
        skills=list(UI_AUTOMATION_EXPERT.skills),
        toolsets=list(UI_AUTOMATION_EXPERT.toolsets),
        mcp_servers=[],
        stats={"bundled": True},
    )
    registry.register(agent)
    subagent_index.sync_agent(agent)
    return agent
