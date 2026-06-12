import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from agent.llm import MockLLMClient, llm_call_adapter
from gateway.platforms.feishu import parse_feishu_webhook
from gateway.run import GatewayRunner
from gateway.webhook_server import create_feishu_app


@pytest.mark.asyncio
async def test_webhook_server_handles_feishu_message(evolux_home):
    client = MockLLMClient(default_content="webhook reply")
    runner = GatewayRunner(home=evolux_home, llm_call=llm_call_adapter(client))
    app = create_feishu_app(runner)

    payload = {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_x"}},
            "message": {
                "chat_id": "oc_1",
                "chat_type": "p2p",
                "content": '{"text":"via http"}',
            },
        },
    }

    async with TestClient(TestServer(app)) as http:
        resp = await http.post("/webhook/feishu/work-bot", json=payload)
        assert resp.status == 200
        body = await resp.json()
        assert body["evolux"]["content"] == "webhook reply"

    runner.shutdown()


@pytest.mark.asyncio
async def test_webhook_server_handles_feishu_card_action(evolux_home):
    client = MockLLMClient(default_content="continued after clarify")
    runner = GatewayRunner(home=evolux_home, llm_call=llm_call_adapter(client))
    app = create_feishu_app(runner)

    payload = {
        "schema": "2.0",
        "header": {"event_type": "card.action.trigger"},
        "event": {
            "operator": {"open_id": "ou_x"},
            "action": {"tag": "button", "value": {"option": "evolux", "question": "Pick repo"}},
            "context": {"open_chat_id": "oc_1", "open_message_id": "om_1", "chat_type": "p2p"},
        },
    }

    async with TestClient(TestServer(app)) as http:
        resp = await http.post("/webhook/feishu/work-bot", json=payload)
        assert resp.status == 200
        body = await resp.json()
        assert body["toast"]["type"] == "success"
        assert "evolux" in body["toast"]["content"]
        assert body["card"]["type"] == "raw"
        assert "evolux" in str(body["card"]["data"])

    runner.shutdown()


@pytest.mark.asyncio
async def test_webhook_health(evolux_home):
    runner = GatewayRunner(
        home=evolux_home,
        llm_call=lambda _: type("R", (), {"content": "ok", "tool_calls": []})(),
    )
    app = create_feishu_app(runner)
    async with TestClient(TestServer(app)) as http:
        resp = await http.get("/health")
        assert resp.status == 200
        assert (await resp.json())["status"] == "ok"
    runner.shutdown()
