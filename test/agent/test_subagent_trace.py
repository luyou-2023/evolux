from agent.trace_hooks import TraceToolHook
from agent.turn_trace import TurnTrace


def test_subagent_tool_hook_prefixes_agent_id():
    trace = TurnTrace()
    hook = TraceToolHook(trace, agent_id="code-expert")
    hook.on_tool_end("1", "terminal", {"command": "pytest"}, "ok")
    assert trace.steps[0].agent_id == "code-expert"
    assert "code-expert" in trace.steps[0].title
