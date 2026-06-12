import asyncio
import json

from gateway.assistant_registry import AssistantRegistry
from gateway.platforms.feishu import parse_feishu_webhook
from gateway.run import GatewayRunner


def test_feishu_message_through_gateway(evolux_home):
    registry = AssistantRegistry(home=evolux_home)
    registry.bind_platform("work-bot", "feishu", {"app_id": "app", "mode": "webhook"})

    payload = {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_x"}},
            "message": {
                "chat_id": "oc_1",
                "chat_type": "p2p",
                "content": '{"text":"飞书消息"}',
            },
        },
    }
    parsed = parse_feishu_webhook(payload, assistant_id="work-bot")
    assert parsed.text == "飞书消息"

    async def _run():
        runner = GatewayRunner(
            home=evolux_home,
            llm_call=lambda _: type("R", (), {"content": "飞书回复", "tool_calls": []})(),
        )
        response = await runner.handle_message(parsed)
        runner.shutdown()
        return response

    response = asyncio.run(_run())
    assert response.content == "飞书回复"
    assert response.assistant_id == "work-bot"
