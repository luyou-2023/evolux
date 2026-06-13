from agent.turn_trace import TurnTrace, format_coordination_summary
from gateway.platforms.feishu_format import build_feishu_post_content


def test_format_coordination_summary_shows_expert_work_not_tools():
    trace = TurnTrace()
    trace.set_routing(skills=["plan", "git"], agents=["git-expert", "mcp-integration-expert"])
    trace.add_tool(
        name="terminal",
        arguments={"command": "cat ~/.hermes/config.yaml"},
        result='{"success": true}',
        agent_id="mcp-integration-expert",
    )
    trace.add_subagent(
        agent_id="mcp-integration-expert",
        task="查询 ls 环境 6669 的 segment 列表",
        summary="返回 100 个 DYNAMIC segment，最大人群 H 共 49777 人",
    )

    lines = format_coordination_summary(trace)
    text = "\n".join(lines)
    assert "mcp-integration-expert" in text
    assert "6669" in text
    assert "49777" in text
    assert "cat ~/.hermes" not in text
    assert "git-expert" not in text or "路由候选" in text


def test_build_feishu_post_hides_nested_tool_noise():
    trace = TurnTrace()
    trace.add_tool(
        name="read_file",
        arguments={"path": "/Users/luke/.hermes/config.yaml"},
        result='{"success": false}',
        agent_id="mcp-integration-expert",
    )
    trace.add_subagent(
        agent_id="cdp-data-expert",
        task="统计 segment",
        summary="共 68 个 segment",
    )
    post = build_feishu_post_content(answer="查询完成", trace=trace)
    flat = str(post["zh_cn"]["content"])
    assert "协调过程" in flat
    assert "cdp-data-expert" in flat
    assert "EVOLUX_HOME" not in flat
    assert "read_file" not in flat
    assert "查询完成" in flat
