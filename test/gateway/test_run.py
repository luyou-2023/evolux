import asyncio

from gateway.activity import get_activity_bus
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


def test_gateway_runner_emits_card_action_activity(evolux_home):
    bus = get_activity_bus()
    before = len(bus.recent(500))
    runner = GatewayRunner(
        home=evolux_home,
        llm_call=lambda _: type("R", (), {"content": "continued", "tool_calls": []})(),
        send_feishu_reply=False,
    )
    payload = {
        "header": {"event_type": "card.action.trigger"},
        "event": {
            "operator": {"open_id": "ou_1"},
            "action": {"value": {"option": "evolux", "question": "Pick repo"}},
            "context": {"open_chat_id": "oc_1", "chat_type": "p2p"},
        },
    }
    event = parse_feishu_webhook(payload, assistant_id="default")
    runner.handle_message_sync(event)
    runner.shutdown()
    recent = bus.recent(500)[before:]
    kinds = [item.kind for item in recent]
    assert "card_action_received" in kinds
    card_events = [item for item in recent if item.kind == "card_action_received"]
    assert card_events[-1].detail == "evolux"
    assert card_events[-1].platform == "feishu"
