from agent.routing import fuse_routing, looks_like_ui_test_task, SubAgentCandidate


def test_looks_like_ui_test_task():
    assert looks_like_ui_test_task("用 Playwright 做 E2E 自动化测试")
    assert looks_like_ui_test_task("点击登录按钮并断言进入首页")


def test_ui_task_boosts_ui_automation_expert():
    candidates = [
        SubAgentCandidate("code-dev-expert", vector_score=0.8, domain="code"),
        SubAgentCandidate("ui-automation-expert", vector_score=0.3, domain="ui-test", skills=["midscene-ui"]),
    ]
    ctx = fuse_routing(
        [],
        candidates,
        user_message="Playwright UI 自动化测试登录流程",
        agent_mcp={},
        agent_domains={"ui-automation-expert": "ui-test", "code-dev-expert": "code"},
    )
    assert ctx.fused_ranking[0].agent_id == "ui-automation-expert"
    assert "UI 自动化" in ctx.prompt_block
