import pytest
from aiohttp.test_utils import TestClient, TestServer

from agent.llm import MockLLMClient, llm_call_adapter
from gateway.run import GatewayRunner
from gateway.webhook_server import create_gateway_app


@pytest.mark.asyncio
async def test_dashboard_activity_page_renders_live_feed(evolux_home):
    runner = GatewayRunner(
        home=evolux_home,
        llm_call=llm_call_adapter(MockLLMClient(default_content="ok")),
        send_feishu_reply=False,
    )
    app = create_gateway_app(runner, evolux_home)
    async with TestClient(TestServer(app)) as http:
        resp = await http.get("/dashboard/activity")
        assert resp.status == 200
        text = await resp.text()
        assert "Live Activity" in text
        assert "/dashboard/events" in text
        assert "EventSource" in text
    runner.shutdown()
