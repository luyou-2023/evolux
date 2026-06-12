import asyncio
from unittest.mock import MagicMock, patch

from gateway.assistant_registry import AssistantRegistry
from gateway.platforms.feishu import parse_feishu_webhook
from gateway.run import GatewayRunner


def test_gateway_sends_feishu_reply(evolux_home):
    registry = AssistantRegistry(home=evolux_home)
    registry.bind_platform(
        "work-bot",
        "feishu",
        {"app_id": "app", "app_secret": "secret", "mode": "webhook"},
    )

    payload = {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_x"}},
            "message": {
                "chat_id": "oc_1",
                "chat_type": "p2p",
                "content": '{"text":"ping"}',
            },
        },
    }
    parsed = parse_feishu_webhook(payload, assistant_id="work-bot")

    mock_client = MagicMock()
    mock_client.send_text.return_value = {"code": 0}

    async def _run():
        runner = GatewayRunner(
            home=evolux_home,
            llm_call=lambda _: type("R", (), {"content": "pong", "tool_calls": []})(),
        )
        with patch.object(runner, "_get_feishu_client", return_value=mock_client):
            response = await runner.handle_message(parsed)
        runner.shutdown()
        return response

    response = asyncio.run(_run())
    assert response.content == "pong"
    assert response.reply_sent is True
    mock_client.send_text.assert_called_once_with("oc_1", "pong")
