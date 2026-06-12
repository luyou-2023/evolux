import json

from agent.tooling import build_combined_tool_executor
from tools.orchestrator_tools import OrchestratorToolContext


def test_combined_executor_runs_builtin_echo():
    ctx = OrchestratorToolContext(
        assistant_id="default",
        agent_registry=None,
        subagent_index=None,
        skill_router=None,
        prepare_routing=lambda q: None,
        create_subagent_runner=lambda **_: None,
        dispatch_subagent=lambda **_: {},
    )
    executor = build_combined_tool_executor(ctx)
    out = executor({"name": "echo", "arguments": {"message": "hi"}})
    assert json.loads(out)["echo"] == "hi"
