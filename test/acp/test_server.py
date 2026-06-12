import pytest

pytest.importorskip("acp")

from acp_adapter.server import EvoluxACPAgent


@pytest.mark.asyncio
async def test_acp_fork_session_endpoint(evolux_home, monkeypatch):
    monkeypatch.setattr("acp_adapter.session.get_evolux_home", lambda: evolux_home)
    monkeypatch.setattr("agent.runtime.get_evolux_home", lambda: evolux_home)
    agent = EvoluxACPAgent()
    parent = await agent.new_session(cwd=str(evolux_home))
    forked = await agent.fork_session(cwd=str(evolux_home), session_id=parent.session_id)
    assert forked.session_id != parent.session_id
    await agent.close_session(parent.session_id)
    await agent.close_session(forked.session_id)


@pytest.mark.asyncio
async def test_acp_load_session_endpoint(evolux_home, monkeypatch):
    monkeypatch.setattr("acp_adapter.session.get_evolux_home", lambda: evolux_home)
    monkeypatch.setattr("agent.runtime.get_evolux_home", lambda: evolux_home)
    agent = EvoluxACPAgent()
    created = await agent.new_session(cwd=str(evolux_home))
    loaded = await agent.load_session(cwd=str(evolux_home), session_id=created.session_id)
    assert loaded is not None
    await agent.close_session(created.session_id)


@pytest.mark.asyncio
async def test_acp_initialize():
    agent = EvoluxACPAgent()
    response = await agent.initialize(protocol_version=1)
    assert response.agent_info.name == "evolux"


@pytest.mark.asyncio
async def test_acp_new_session_and_prompt(monkeypatch, evolux_home):
    agent = EvoluxACPAgent()

    class FakeResult:
        content = "pong"

    def fake_turn(self, session_key, user_message, platform="cli", **kwargs):
        return FakeResult()

    monkeypatch.setattr("run_agent.EvoluxAgent.run_orchestrator_turn", fake_turn)

    session = await agent.new_session(cwd=str(evolux_home))
    from acp.schema import TextContentBlock

    response = await agent.prompt(
        [TextContentBlock(type="text", text="ping")],
        session_id=session.session_id,
    )
    assert response.stop_reason == "end_turn"
    await agent.close_session(session.session_id)
