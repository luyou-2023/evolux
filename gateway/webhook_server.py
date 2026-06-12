"""Feishu webhook HTTP server and unified gateway app."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Callable

from gateway.dashboard import register_dashboard_routes
from gateway.platforms.feishu import build_card_action_ack, parse_feishu_webhook, verify_feishu_signature
from gateway.platforms.feishu_format import build_clarify_selected_card
from gateway.run import GatewayRunner

logger = logging.getLogger("evolux.gateway.webhook")

try:
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:
    web = None  # type: ignore[assignment,misc]
    AIOHTTP_AVAILABLE = False


def create_gateway_app(
    runner: GatewayRunner,
    home: Path,
    *,
    get_secret: Callable[[str], str] | None = None,
    enable_dashboard: bool = True,
) -> "web.Application":
    if not AIOHTTP_AVAILABLE:
        raise RuntimeError("aiohttp is required for gateway server: pip install evolux[gateway]")

    app = web.Application()

    async def feishu_webhook(request: web.Request) -> web.Response:
        assistant_id = request.match_info["assistant_id"]
        body = await request.read()

        secret = (get_secret(assistant_id) if get_secret else "") or ""
        timestamp = request.headers.get("X-Lark-Request-Timestamp", "")
        nonce = request.headers.get("X-Lark-Request-Nonce", "")
        signature = request.headers.get("X-Lark-Signature", "")
        if secret and not verify_feishu_signature(timestamp, nonce, body, secret, signature):
            return web.json_response({"error": "invalid signature"}, status=401)

        payload = json.loads(body.decode("utf-8"))
        parsed = parse_feishu_webhook(payload, assistant_id=assistant_id)
        if isinstance(parsed, dict):
            return web.json_response(parsed)

        if parsed is None:
            return web.json_response({})

        response = await runner.handle_message(parsed)
        logger.info(
            "handled feishu %s assistant=%s session=%s reply_sent=%s",
            "card_action" if parsed.is_card_action else "message",
            assistant_id,
            response.session_key,
            response.reply_sent,
        )
        if parsed.is_card_action:
            option = parsed.card_action_option
            toast = f"已选择：{option}" if option else "已收到您的选择"
            selected_card = None
            if option:
                selected_card = build_clarify_selected_card(
                    question=parsed.card_action_question or "",
                    option=option,
                )
            return web.json_response(build_card_action_ack(toast, card=selected_card))

        return web.json_response(
            {
                "evolux": {
                    "assistant_id": response.assistant_id,
                    "session_key": response.session_key,
                    "content": response.content,
                    "reply_sent": response.reply_sent,
                    "reply_error": response.reply_error,
                }
            }
        )

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "evolux-gateway"})

    app.router.add_get("/health", health)
    app.router.add_post("/webhook/feishu/{assistant_id}", feishu_webhook)
    if enable_dashboard:
        register_dashboard_routes(app, home)
    return app


def create_feishu_app(
    runner: GatewayRunner,
    *,
    get_secret: Callable[[str], str] | None = None,
    home: Path | None = None,
) -> "web.Application":
    """Backward-compatible alias that includes dashboard when home is provided."""
    from evolux_constants import get_evolux_home

    return create_gateway_app(
        runner,
        home or get_evolux_home(),
        get_secret=get_secret,
        enable_dashboard=True,
    )


async def run_webhook_server(
    runner: GatewayRunner,
    host: str,
    port: int,
    home: Path,
    *,
    get_secret: Callable[[str], str] | None = None,
) -> None:
    app = create_gateway_app(runner, home, get_secret=get_secret)
    runner_ref = runner

    async def _cleanup(_app: web.Application) -> None:
        runner_ref.shutdown()

    app.on_cleanup.append(_cleanup)
    web_runner = web.AppRunner(app)
    await web_runner.setup()
    site = web.TCPSite(web_runner, host=host, port=port)
    await site.start()
    logger.info("Evolux gateway listening on http://%s:%s", host, port)

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await web_runner.cleanup()
