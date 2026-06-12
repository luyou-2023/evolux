import pytest

pytest.importorskip("acp")

from acp_adapter.session import AcpSessionManager, apply_session_mcp_servers
from test.fixtures.minimal_mcp_http_server import start_server


@pytest.fixture
def acp_manager(evolux_home, monkeypatch):
    monkeypatch.setattr("acp_adapter.session.get_evolux_home", lambda: evolux_home)
    monkeypatch.setattr("agent.runtime.get_evolux_home", lambda: evolux_home)
    return AcpSessionManager()


def test_acp_load_session_restores_persisted_session(acp_manager, evolux_home, monkeypatch):
    monkeypatch.setattr("acp_adapter.session.get_evolux_home", lambda: evolux_home)
    created = acp_manager.create_session(cwd="/tmp/project")
    session_id = created.session_id
    session_key = created.session_key

    restarted = AcpSessionManager()
    state = restarted.load_session(session_id, cwd="/tmp/project")
    assert state is not None
    assert state.session_key == session_key
    restarted.close_session(session_id)


def test_apply_session_mcp_servers_registers_http_tools(acp_manager):
    url, stop = start_server()
    try:
        state = acp_manager.create_session(cwd="/tmp/project")
        names = apply_session_mcp_servers(
            state.agent,
            [{"name": "echo", "url": url}],
        )
        assert names == ["echo"]
        tools = state.agent.mcp_manager.discover_tools("echo")
        assert tools[0]["name"] == "mcp_echo_echo"
        state.agent.close()
    finally:
        stop()
