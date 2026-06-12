import pytest
from aiohttp.test_utils import TestClient, TestServer

from agent.llm import MockLLMClient, llm_call_adapter
from evolux_state import SessionDB
from gateway.run import GatewayRunner
from gateway.webhook_server import create_gateway_app


@pytest.mark.asyncio
async def test_dashboard_overview(evolux_home):
    runner = GatewayRunner(
        home=evolux_home,
        llm_call=llm_call_adapter(MockLLMClient(default_content="ok")),
        send_feishu_reply=False,
    )
    app = create_gateway_app(runner, evolux_home)
    async with TestClient(TestServer(app)) as http:
        resp = await http.get("/dashboard")
        assert resp.status == 200
        text = await resp.text()
        assert "Evolux Dashboard" in text
    runner.shutdown()


@pytest.mark.asyncio
async def test_dashboard_session_detail(evolux_home):
    db = SessionDB(home=evolux_home)
    session_key = "orchestrator:default:cli:dm:test"
    session_id = db.get_or_create_session(session_key, "default", "cli")
    db.set_session_title(session_key, "Dashboard Test")
    db.append_message(session_id, "user", "hello dashboard")
    db.append_message(session_id, "assistant", "hi there")
    db.close()

    runner = GatewayRunner(
        home=evolux_home,
        llm_call=llm_call_adapter(MockLLMClient(default_content="ok")),
        send_feishu_reply=False,
    )
    app = create_gateway_app(runner, evolux_home)
    async with TestClient(TestServer(app)) as http:
        resp = await http.get("/dashboard/sessions/orchestrator%3Adefault%3Acli%3Adm%3Atest")
        assert resp.status == 200
        text = await resp.text()
        assert "hello dashboard" in text
        assert "hi there" in text
        assert "Dashboard Test" in text
    runner.shutdown()
