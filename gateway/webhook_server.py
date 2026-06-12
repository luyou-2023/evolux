"""Feishu webhook HTTP server."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable

from gateway.platforms.feishu import parse_feishu_webhook, verify_feishu_signature
from gateway.run import GatewayRunner

logger = logging.getLogger("evolux.gateway.webhook")

try:
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:
    web = None  # type: ignore[assignment,misc]
    AIOHTTP_AVAILABLE = False


def create_feishu_app(
    runner: GatewayRunner,
    *,
    get_secret: Callable[[str], str] | None = None,
) -> "web.Application":
    if not AIOHTTP_AVAILABLE:
        raise RuntimeError("aiohttp is required for webhook server: pip install evolux[gateway]")

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
            "handled feishu message assistant=%s session=%s",
            assistant_id,
            response.session_key,
        )
        return web.json_response(
            {
                "evolux": {
                    "assistant_id": response.assistant_id,
                    "session_key": response.session_key,
                    "content": response.content,
                }
            }
        )

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "evolux-gateway"})

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_post("/webhook/feishu/{assistant_id}", feishu_webhook)
    return app


async def run_webhook_server(
    runner: GatewayRunner,
    host: str,
    port: int,
    *,
    get_secret: Callable[[str], str] | None = None,
) -> None:
    app = create_feishu_app(runner, get_secret=get_secret)
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
