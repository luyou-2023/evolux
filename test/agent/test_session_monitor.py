import json

from agent.agent_registry import AgentRegistry
from agent.session_monitor import (
    SESSION_MONITOR_AGENT_ID,
    SessionMonitorHook,
    ensure_session_monitor_agent,
    format_progress_end,
    format_progress_start,
    is_internal_agent,
    turn_start_message,
)
from gateway.activity import get_activity_bus
from run_agent import EvoluxAgent


def test_is_internal_agent():
    assert is_internal_agent("_session-monitor") is True
    assert is_internal_agent("writer") is False


def test_ensure_session_monitor_agent_registers_internal_agent(evolux_home):
    registry = AgentRegistry(home=evolux_home)
    agent = ensure_session_monitor_agent(registry, "default")
    assert agent.agent_id == SESSION_MONITOR_AGENT_ID
    assert agent.stats.get("internal") is True
    again = ensure_session_monitor_agent(registry, "default")
    assert again.agent_id == SESSION_MONITOR_AGENT_ID


def test_format_progress_messages():
    start = format_progress_start("dispatch_subagent", {"agent_id": "writer", "task": "draft doc"})
    assert "writer" in start
    assert "draft doc" in start
    end = format_progress_end(
        "dispatch_subagent",
        {"agent_id": "writer"},
        json.dumps({"content": "done", "exhausted": False}),
    )
    assert "writer" in end
    assert "done" in end


def test_session_monitor_hook_emits_progress_update(evolux_home):
    bus = get_activity_bus()
    before = len(bus.recent(500))
    messages: list[str] = []
    hook = SessionMonitorHook(
        session_key="orchestrator:default:cli:dm:local",
        assistant_id="default",
        platform="cli",
        on_progress=messages.append,
    )
    hook.push(turn_start_message("hello"))
    hook.on_tool_start("1", "dispatch_subagent", {"agent_id": "writer", "task": "write"})
    hook.on_tool_end(
        "1",
        "dispatch_subagent",
        {"agent_id": "writer"},
        json.dumps({"content": "ok", "exhausted": False}),
    )
    recent = bus.recent(500)[before:]
    assert any(item.kind == "progress_update" for item in recent)
    assert messages
    assert hook.subagent_dispatches == 1


def test_evolux_agent_bootstraps_session_monitor(evolux_home):
    agent = EvoluxAgent(
        llm_call=lambda _: type("R", (), {"content": "ok", "tool_calls": []})(),
        home=evolux_home,
    )
    registered = agent.agent_registry.get(SESSION_MONITOR_AGENT_ID)
    assert registered is not None
    assert registered.stats.get("internal") is True
    agent.close()
