from run_agent import EvoluxAgent


def test_evolux_agent_persists_orchestrator_turn(evolux_home):
    agent = EvoluxAgent(
        home=evolux_home,
        llm_call=lambda messages: type(
            "R",
            (),
            {"content": "saved reply", "tool_calls": []},
        )(),
    )
    key = "orchestrator:default:cli:dm:user1"
    result = agent.run_orchestrator_turn(key, "hello")
    assert result.content == "saved reply"

    session_id = agent.session_db.get_session_id_by_key(key)
    messages = agent.session_db.get_messages(session_id)
    assert messages[-2]["content"] == "hello"
    assert messages[-1]["content"] == "saved reply"
    agent.close()
