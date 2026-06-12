from agent.turn_trace import TurnTrace, categorize_tool, tool_title


def test_categorize_tool():
    assert categorize_tool("mcp_echo_echo") == "mcp"
    assert categorize_tool("dispatch_subagent") == "orchestrator"
    assert categorize_tool("terminal") == "builtin"


def test_turn_trace_records_tool_and_subagent():
    trace = TurnTrace()
    trace.set_routing(skills=["git"], agents=["code-expert"])
    trace.add_tool(name="mcp_echo_echo", arguments={"text": "hi"}, result='{"ok": true}')
    trace.add_subagent(agent_id="code-expert", task="fix bug", summary="done")
    assert trace.routing_skills == ["git"]
    assert len(trace.steps) == 2
    assert trace.steps[0].category == "mcp"
    assert trace.steps[1].category == "subagent"


def test_tool_title_mcp():
    assert "MCP" in tool_title("mcp_echo_echo", {})
