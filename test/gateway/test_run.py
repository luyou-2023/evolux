import asyncio

from gateway.events import MessageEvent
from gateway.platforms.feishu import parse_feishu_webhook
from gateway.run import GatewayRunner
from gateway.session import SessionSource


def test_gateway_runner_handle_message_sync(evolux_home):
    runner = GatewayRunner(
        home=evolux_home,
        llm_call=lambda _: type("R", (), {"content": "gateway reply", "tool_calls": []})(),
    )
    event = MessageEvent(
        assistant_id="default",
        source=SessionSource(platform="cli", chat_type="dm", chat_id="user1"),
        text="hello gateway",
    )
    response = runner.handle_message_sync(event)
    assert response.content == "gateway reply"
    assert response.session_key.startswith("orchestrator:default:cli:dm:")
    runner.shutdown()


def test_gateway_runner_handle_message_async(evolux_home):
    async def _run():
        runner = GatewayRunner(
            home=evolux_home,
            llm_call=lambda _: type("R", (), {"content": "async reply", "tool_calls": []})(),
        )
        event = MessageEvent(
            assistant_id="default",
            source=SessionSource(platform="cli", chat_type="dm", chat_id="user1"),
            text="ping",
        )
        response = await runner.handle_message(event)
        runner.shutdown()
        return response

    response = asyncio.run(_run())
    assert response.content == "async reply"
