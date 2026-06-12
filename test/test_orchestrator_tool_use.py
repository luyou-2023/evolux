import json

from run_agent import EvoluxAgent


def test_orchestrator_turn_executes_skills_list_tool(evolux_home):
    step = {"n": 0}

    def llm_call(messages, **kwargs):
        if step["n"] == 0:
            step["n"] += 1
            return type(
                "R",
                (),
                {
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "tc-skills",
                            "type": "function",
                            "function": {"name": "skills_list", "arguments": "{}"},
                        }
                    ],
                },
            )()
        return type("R", (), {"content": "listed skills", "tool_calls": []})()

    agent = EvoluxAgent(llm_call=llm_call, home=evolux_home, assistant_id="default")
    result = agent.run_orchestrator_turn(
        "orchestrator:default:cli:dm:tool-use",
        "show skills",
        platform="cli",
    )

    assert result.content == "listed skills"
    tool_messages = [message for message in result.messages if message.get("role") == "tool"]
    assert len(tool_messages) == 1
    payload = json.loads(tool_messages[0]["content"])
    assert payload.get("success") is True
    assert isinstance(payload.get("skills"), list)
    assert step["n"] == 1
    agent.close()
