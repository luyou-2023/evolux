from agent.conversation_loop import run_conversation_loop
from agent.turn_cancel import bind_session_key, clear_turn_cancel, request_turn_cancel, unbind_session_key


def test_conversation_loop_stops_when_cancel_requested():
    calls = {"n": 0}

    def llm_call(_messages, **kwargs):
        calls["n"] += 1
        return type(
            "R",
            (),
            {
                "content": None,
                "tool_calls": [{"id": "1", "type": "function", "function": {"name": "noop", "arguments": "{}"}}],
            },
        )()

    def executor(_tool_call):
        request_turn_cancel("session:test")
        return "ok"

    token = bind_session_key("session:test")
    clear_turn_cancel("session:test")
    try:
        result = run_conversation_loop(
            messages=[{"role": "user", "content": "go"}],
            llm_call=llm_call,
            max_iterations=5,
            tool_executor=executor,
        )
    finally:
        unbind_session_key(token)

    assert result.content == "已停止当前任务。"
    assert result.plain_reply is True
