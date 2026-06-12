from agent.conversation_loop import run_conversation_loop
from agent.tool_hooks import wrap_tool_executor


class RecordingHook:
    def __init__(self):
        self.events: list[tuple[str, str]] = []

    def on_tool_start(self, tool_call_id, name, arguments):
        self.events.append(("start", name))

    def on_tool_end(self, tool_call_id, name, arguments, result):
        self.events.append(("end", name))


def test_tool_hook_wraps_executor():
    hook = RecordingHook()

    def executor(call):
        return "ok"

    wrapped = wrap_tool_executor(executor, hook)
    wrapped({"id": "1", "name": "terminal", "arguments": {"command": "echo"}})
    assert hook.events == [("start", "terminal"), ("end", "terminal")]


def test_conversation_loop_invokes_tool_hook():
    hook = RecordingHook()
    calls = [{"id": "c1", "name": "todo", "arguments": {}}]
    state = {"turn": 0}

    def llm_call(messages):
        state["turn"] += 1

        class Response:
            content = "done" if state["turn"] > 1 else None
            tool_calls = calls if state["turn"] == 1 else []

        return Response()

    def executor(call):
        return '{"success": true}'

    result = run_conversation_loop(
        [{"role": "user", "content": "plan"}],
        llm_call=llm_call,
        max_iterations=3,
        tool_executor=executor,
        tool_hook=hook,
    )
    assert result.content == "done"
    assert ("start", "todo") in hook.events
    assert ("end", "todo") in hook.events
