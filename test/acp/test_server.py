import pytest

pytest.importorskip("acp")

from acp_adapter.server import EvoluxACPAgent


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
