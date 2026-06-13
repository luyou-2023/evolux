"""Tests for Feishu WebSocket long connection."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from gateway.assistant_registry import AssistantRegistry
from gateway.platforms.feishu import (
    feishu_connection_mode,
    parse_feishu_card_action_sdk,
    parse_feishu_im_receive_sdk,
)
from gateway.platforms.feishu_ws import FeishuWebSocketManager


def test_feishu_connection_mode_defaults_to_websocket():
    assert feishu_connection_mode({}) == "websocket"
    assert feishu_connection_mode({"mode": "webhook"}) == "webhook"
    assert feishu_connection_mode({"mode": "websocket"}) == "websocket"
    assert feishu_connection_mode({"mode": "invalid"}) == "websocket"


def test_parse_feishu_im_receive_sdk():
    data = SimpleNamespace(
        event=SimpleNamespace(
            sender=SimpleNamespace(
                sender_id=SimpleNamespace(open_id="ou_x", user_id="", union_id="on_x"),
            ),
            message=SimpleNamespace(
                message_id="om_1",
                chat_id="oc_1",
                chat_type="p2p",
                thread_id="",
                content='{"text":"你好"}',
            ),
        )
    )
    event = parse_feishu_im_receive_sdk(data, assistant_id="work-bot")
    assert event is not None
    assert event.text == "你好"
    assert event.source.chat_type == "dm"
    assert event.source.user_id == "ou_x"
    assert event.assistant_id == "work-bot"


def test_parse_feishu_card_action_sdk():
    data = SimpleNamespace(
        event=SimpleNamespace(
            operator=SimpleNamespace(open_id="ou_card", union_id="on_card"),
            action=SimpleNamespace(
                tag="button",
                value={"option": "evolux", "question": "Which repo?"},
            ),
            context=SimpleNamespace(
                open_chat_id="oc_card",
                open_message_id="om_card",
                chat_type="p2p",
            ),
        )
    )
    event = parse_feishu_card_action_sdk(data, assistant_id="work-bot")
    assert event.is_card_action is True
    assert event.card_action_option == "evolux"
    assert event.text == "[确认] Which repo? → evolux"
    assert event.source.chat_id == "oc_card"


@pytest.mark.asyncio
async def test_ws_manager_starts_only_websocket_assistants(evolux_home, monkeypatch):
    registry = AssistantRegistry(home=evolux_home)
    registry.bind_platform(
        "ws-bot",
        "feishu",
        {"app_id": "app_ws", "app_secret": "secret_ws", "mode": "websocket"},
    )
    registry.bind_platform(
        "hook-bot",
        "feishu",
        {"app_id": "app_hook", "app_secret": "secret_hook", "mode": "webhook"},
    )

    started: list[str] = []

    class FakeClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def start(self):
            started.append(self.kwargs["assistant_id"])

        async def stop(self):
            pass

    monkeypatch.setattr("gateway.platforms.feishu_ws.FeishuWebSocketClient", FakeClient)
    manager = FeishuWebSocketManager(runner=object())
    await manager.start_for_registry(registry)
    assert started == ["ws-bot"]
    await manager.stop()
