from run_agent import EvoluxAgent


def test_orchestrator_turn_passes_tool_definitions_to_llm(evolux_home):
    seen = {"tools": None}

    def llm_call(messages, **kwargs):
        seen["tools"] = kwargs.get("tools")
        return type("R", (), {"content": "ok", "tool_calls": []})()

    agent = EvoluxAgent(llm_call=llm_call, home=evolux_home, assistant_id="default")
    agent.run_orchestrator_turn("orchestrator:default:cli:dm:test", "hello", platform="cli")
    assert seen["tools"]
    tool_names = {item["function"]["name"] for item in seen["tools"] if item.get("function")}
    assert "skills_list" in tool_names
    assert "dispatch_subagent" in tool_names
    agent.close()
