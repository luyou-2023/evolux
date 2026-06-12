from agent.config import DEFAULT_ORCHESTRATOR_MAX_ITERATIONS, DEFAULT_SUBAGENT_MAX_ITERATIONS
from agent.orchestrator import OrchestratorAgent
from agent.subagent import SubAgent


def test_orchestrator_default_max_iterations_is_30():
    agent = OrchestratorAgent(llm_call=lambda _: None)
    assert agent.max_iterations == DEFAULT_ORCHESTRATOR_MAX_ITERATIONS
    assert agent.max_iterations == 30


def test_orchestrator_run_turn_with_mock_llm():
    agent = OrchestratorAgent(
        llm_call=lambda messages: type(
            "R",
            (),
            {"content": "orchestrator reply", "tool_calls": []},
        )()
    )
    result = agent.run_turn([{"role": "user", "content": "hello"}])
    assert result.content == "orchestrator reply"
    assert result.exhausted is False


def test_subagent_default_max_iterations_is_90():
    agent = SubAgent(agent_id="code-expert", llm_call=lambda _: None)
    assert agent.max_iterations == DEFAULT_SUBAGENT_MAX_ITERATIONS
    assert agent.max_iterations == 90


def test_subagent_run_task_with_mock_llm():
    agent = SubAgent(
        agent_id="code-expert",
        llm_call=lambda messages: type(
            "R",
            (),
            {"content": "subagent done", "tool_calls": []},
        )(),
    )
    result = agent.run_task("fix bug", context_slice="file foo.py")
    assert result.content == "subagent done"
