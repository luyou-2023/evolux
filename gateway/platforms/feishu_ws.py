"""Feishu WebSocket long connection (Hermes-aligned, no public URL required)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from gateway.assistant_registry import AssistantRegistry
from gateway.platforms.feishu import feishu_connection_mode, parse_feishu_card_action_sdk, parse_feishu_im_receive_sdk
from gateway.platforms.feishu_format import build_clarify_selected_card

logger = logging.getLogger("evolux.gateway.feishu_ws")

try:
    import lark_oapi as lark
    from lark_oapi.core.const import FEISHU_DOMAIN
    from lark_oapi.event.callback.model.p2_card_action_trigger import (
        CallBackCard,
        CallBackToast,
        P2CardActionTriggerResponse,
    )
    from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
    from lark_oapi.ws import Client as FeishuWSClient

    LARK_OAPI_AVAILABLE = True
except ImportError:
    lark = None  # type: ignore[assignment]
    FEISHU_DOMAIN = None  # type: ignore[assignment]
    CallBackCard = None  # type: ignore[assignment,misc]
    CallBackToast = None  # type: ignore[assignment,misc]
    P2CardActionTriggerResponse = None  # type: ignore[assignment,misc]
    EventDispatcherHandler = None  # type: ignore[assignment,misc]
    FeishuWSClient = None  # type: ignore[assignment,misc]
    LARK_OAPI_AVAILABLE = False

try:
    import websockets  # noqa: F401

    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

FEISHU_WS_AVAILABLE = LARK_OAPI_AVAILABLE and WEBSOCKETS_AVAILABLE


def _run_ws_client(ws_client: Any, adapter: FeishuWebSocketClient) -> None:
    """Run the official Lark WS client in a dedicated thread."""
    import lark_oapi.ws.client as ws_client_module

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    ws_client_module.loop = loop
    adapter._ws_thread_loop = loop
    try:
        ws_client.start()
    except Exception:
        logger.exception("Feishu WebSocket client stopped with error")
    finally:
        adapter._ws_thread_loop = None
        pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        try:
            loop.close()
        except Exception:
            pass


class FeishuWebSocketClient:
    """Maintain one outbound WebSocket per Feishu app / assistant."""

    def __init__(
        self,
        *,
        assistant_id: str,
        app_id: str,
        app_secret: str,
        runner: Any,
        verification_token: str = "",
        encrypt_key: str = "",
    ):
        self.assistant_id = assistant_id
        self.app_id = app_id
        self.app_secret = app_secret
        self.runner = runner
        self.verification_token = verification_token
        self.encrypt_key = encrypt_key
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws_client: Any = None
        self._ws_future: asyncio.Future[Any] | None = None
        self._ws_thread_loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        if not FEISHU_WS_AVAILABLE:
            raise RuntimeError(
                "Feishu WebSocket requires lark-oapi and websockets: pip install evolux[gateway]"
            )
        if EventDispatcherHandler is None or FeishuWSClient is None or lark is None:
            raise RuntimeError("Feishu WebSocket dependencies are not available")

        self._loop = asyncio.get_running_loop()
        handler = self._build_event_handler()
        self._ws_client = FeishuWSClient(
            app_id=self.app_id,
            app_secret=self.app_secret,
            log_level=lark.LogLevel.INFO,
            event_handler=handler,
            domain=FEISHU_DOMAIN,
        )
        self._ws_future = self._loop.run_in_executor(None, _run_ws_client, self._ws_client, self)
        logger.info(
            "Feishu WebSocket started assistant=%s app_id=%s",
            self.assistant_id,
            self.app_id,
        )

    async def stop(self) -> None:
        if self._ws_client is not None:
            try:
                setattr(self._ws_client, "_auto_reconnect", False)
            except Exception:
                pass
            self._ws_client = None

        ws_future = self._ws_future
        if ws_future is not None:
            try:
                await asyncio.wait_for(asyncio.shield(ws_future), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Feishu WebSocket thread did not exit within 10s assistant=%s", self.assistant_id)
            except Exception:
                logger.debug("Feishu WebSocket thread exit error assistant=%s", self.assistant_id, exc_info=True)

        self._ws_future = None
        self._loop = None

    def _build_event_handler(self) -> Any:
        return (
            EventDispatcherHandler.builder(self.encrypt_key, self.verification_token)
            .register_p2_im_message_receive_v1(self._on_message_event)
            .register_p2_card_action_trigger(self._on_card_action_trigger)
            .build()
        )

    def _on_message_event(self, data: Any) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            logger.warning("Dropping Feishu message: gateway loop not ready assistant=%s", self.assistant_id)
            return
        event = parse_feishu_im_receive_sdk(data, assistant_id=self.assistant_id)
        if event is None:
            return
        asyncio.run_coroutine_threadsafe(self._handle_message(event), loop)

    def _on_card_action_trigger(self, data: Any) -> Any:
        loop = self._loop
        event = parse_feishu_card_action_sdk(data, assistant_id=self.assistant_id)
        if loop is not None and not loop.is_closed():
            asyncio.run_coroutine_threadsafe(self._handle_message(event), loop)

        if P2CardActionTriggerResponse is None or CallBackToast is None:
            return None

        option = event.card_action_option or ""
        toast_content = f"已选择：{option}" if option else "已收到您的选择"
        response = P2CardActionTriggerResponse()
        toast = CallBackToast()
        toast.type = "success"
        toast.content = toast_content
        response.toast = toast
        if option and CallBackCard is not None:
            card = CallBackCard()
            card.type = "raw"
            card.data = build_clarify_selected_card(
                question=event.card_action_question or "",
                option=option,
            )
            response.card = card
        return response

    async def _handle_message(self, event: Any) -> None:
        try:
            response = await self.runner.handle_message(event)
            logger.info(
                "handled feishu ws %s assistant=%s session=%s reply_sent=%s",
                "card_action" if event.is_card_action else "message",
                event.assistant_id,
                response.session_key,
                response.reply_sent,
            )
        except Exception:
            logger.exception("Feishu WebSocket message handling failed assistant=%s", self.assistant_id)


class FeishuWebSocketManager:
    """Start/stop WebSocket clients for all websocket-mode assistants."""

    def __init__(self, runner: Any):
        self.runner = runner
        self._clients: dict[str, FeishuWebSocketClient] = {}

    async def start_for_registry(self, registry: AssistantRegistry) -> None:
        for item in registry.list():
            feishu = item.platforms.get("feishu") or {}
            if feishu_connection_mode(feishu) != "websocket":
                continue
            app_id = str(feishu.get("app_id") or "")
            app_secret = str(feishu.get("app_secret") or "")
            if not app_id or not app_secret:
                logger.warning(
                    "Skipping Feishu WebSocket assistant=%s: missing app_id/app_secret",
                    item.assistant_id,
                )
                continue
            client = FeishuWebSocketClient(
                assistant_id=item.assistant_id,
                app_id=app_id,
                app_secret=app_secret,
                runner=self.runner,
                verification_token=str(feishu.get("verification_token") or ""),
                encrypt_key=str(feishu.get("encrypt_key") or ""),
            )
            await client.start()
            self._clients[item.assistant_id] = client

    async def stop(self) -> None:
        for client in self._clients.values():
            await client.stop()
        self._clients.clear()
