from gateway.platforms.feishu_format import build_feishu_post_content
from agent.turn_trace import TurnTrace


def test_build_feishu_post_includes_trace_and_answer():
    trace = TurnTrace()
    trace.set_routing(skills=["plan"], agents=["writer"])
    trace.add_tool(name="dispatch_subagent", arguments={"agent_id": "writer"}, result='{"content":"ok"}')
    post = build_feishu_post_content(answer="hello user", trace=trace)
    assert post["zh_cn"]["title"] == "Evolux"
    flat = str(post["zh_cn"]["content"])
    assert "协调过程" in flat
    assert "hello user" in flat
    assert "Skill" in flat
