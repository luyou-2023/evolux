"""Feishu webhook HTTP server and unified gateway app."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Callable

from gateway.dashboard import register_dashboard_routes
from gateway.platforms.feishu import build_card_action_ack, parse_feishu_webhook, verify_feishu_signature
from gateway.platforms.feishu_format import build_clarify_selected_card
from gateway.platforms.feishu_hermes import HERMES_DEFAULT_FEISHU_WEBHOOK_PATH
from gateway.run import GatewayRunner

logger = logging.getLogger("evolux.gateway.webhook")

try:
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:
    web = None  # type: ignore[assignment,misc]
    AIOHTTP_AVAILABLE = False


async def _handle_feishu_webhook_request(
    request: web.Request,
    *,
    runner: GatewayRunner,
    assistant_id: str,
    get_secret: Callable[[str], str] | None,
) -> web.Response:
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


def register_feishu_webhook_routes(
    app: "web.Application",
    runner: GatewayRunner,
    *,
    get_secret: Callable[[str], str] | None = None,
    hermes_compat_assistant: str | None = None,
) -> None:
    async def feishu_webhook(request: web.Request) -> web.Response:
        assistant_id = request.match_info["assistant_id"]
        return await _handle_feishu_webhook_request(
            request,
            runner=runner,
            assistant_id=assistant_id,
            get_secret=get_secret,
        )

    app.router.add_post("/webhook/feishu/{assistant_id}", feishu_webhook)

    if hermes_compat_assistant:

        async def hermes_feishu_webhook(request: web.Request) -> web.Response:
            return await _handle_feishu_webhook_request(
                request,
                runner=runner,
                assistant_id=hermes_compat_assistant,
                get_secret=get_secret,
            )

        app.router.add_post(HERMES_DEFAULT_FEISHU_WEBHOOK_PATH, hermes_feishu_webhook)


def create_gateway_app(
    runner: GatewayRunner,
    home: Path,
    *,
    get_secret: Callable[[str], str] | None = None,
    enable_dashboard: bool = True,
    hermes_compat_assistant: str | None = None,
    include_feishu_webhooks: bool = True,
) -> "web.Application":
    if not AIOHTTP_AVAILABLE:
        raise RuntimeError("aiohttp is required for gateway server: pip install evolux[gateway]")

    app = web.Application()

    async def health(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok", "service": "evolux-gateway"})

    app.router.add_get("/health", health)
    if include_feishu_webhooks:
        register_feishu_webhook_routes(
            app,
            runner,
            get_secret=get_secret,
            hermes_compat_assistant=hermes_compat_assistant,
        )
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


def _needs_feishu_webhook_server(registry: Any) -> bool:
    from gateway.platforms.feishu import feishu_connection_mode, feishu_skips_evolux_transport

    for item in registry.list():
        feishu = item.platforms.get("feishu") or {}
        if "feishu" not in item.platforms:
            continue
        if feishu_skips_evolux_transport(feishu):
            continue
        if feishu_connection_mode(feishu) == "webhook":
            return True
    return False


def _default_hermes_compat_assistant(registry: Any, *, hermes_compat: bool) -> str | None:
    if not hermes_compat:
        return None
    from gateway.platforms.feishu import feishu_connection_mode, feishu_skips_evolux_transport

    webhook_assistants = []
    for item in registry.list():
        feishu = item.platforms.get("feishu") or {}
        if "feishu" not in item.platforms:
            continue
        if feishu_skips_evolux_transport(feishu):
            continue
        if feishu_connection_mode(feishu) == "webhook":
            webhook_assistants.append(item.assistant_id)
    if len(webhook_assistants) == 1:
        return webhook_assistants[0]
    return webhook_assistants[0] if webhook_assistants else None


async def run_webhook_server(
    runner: GatewayRunner,
    host: str,
    port: int,
    home: Path,
    *,
    get_secret: Callable[[str], str] | None = None,
    registry: Any | None = None,
    feishu_webhook_host: str | None = None,
    feishu_webhook_port: int | None = None,
    hermes_compat: bool = True,
) -> None:
    from agent.settings import load_settings
    from gateway.assistant_registry import AssistantRegistry
    from gateway.platforms.feishu_ws import FeishuWebSocketManager

    assistant_registry = registry or AssistantRegistry(home=home)
    settings = load_settings(home)
    compat_assistant = _default_hermes_compat_assistant(
        assistant_registry,
        hermes_compat=hermes_compat if hermes_compat is not None else settings.gateway.hermes_compat,
    )
    webhook_host = feishu_webhook_host or settings.gateway.feishu_webhook_host
    webhook_port = (
        feishu_webhook_port
        if feishu_webhook_port is not None
        else settings.gateway.feishu_webhook_port
    )

    use_dedicated_feishu_port = (
        bool(webhook_port)
        and webhook_port > 0
        and webhook_port != port
        and _needs_feishu_webhook_server(assistant_registry)
    )
    main_includes_webhooks = not use_dedicated_feishu_port

    app = create_gateway_app(
        runner,
        home,
        get_secret=get_secret,
        hermes_compat_assistant=compat_assistant if main_includes_webhooks else None,
        include_feishu_webhooks=main_includes_webhooks,
    )
    runner_ref = runner
    ws_manager = FeishuWebSocketManager(runner)
    feishu_runner: web.AppRunner | None = None

    async def _cleanup(_app: web.Application) -> None:
        await ws_manager.stop()
        if feishu_runner is not None:
            await feishu_runner.cleanup()
        runner_ref.shutdown()

    app.on_cleanup.append(_cleanup)
    web_runner = web.AppRunner(app)
    await web_runner.setup()
    site = web.TCPSite(web_runner, host=host, port=port)
    await site.start()
    logger.info("Evolux gateway listening on http://%s:%s", host, port)

    if use_dedicated_feishu_port:
        feishu_app = create_gateway_app(
            runner,
            home,
            get_secret=get_secret,
            enable_dashboard=False,
            hermes_compat_assistant=compat_assistant,
            include_feishu_webhooks=True,
        )
        feishu_runner = web.AppRunner(feishu_app)
        await feishu_runner.setup()
        feishu_site = web.TCPSite(feishu_runner, host=webhook_host, port=int(webhook_port))
        await feishu_site.start()
        logger.info(
            "Feishu webhook (Hermes-compatible) on http://%s:%s%s and /webhook/feishu/<assistant_id>",
            webhook_host,
            webhook_port,
            HERMES_DEFAULT_FEISHU_WEBHOOK_PATH,
        )

    await ws_manager.start_for_registry(assistant_registry)

    cron_task: asyncio.Task | None = asyncio.create_task(_run_cron_ticker(home))
    app["_cron_task"] = cron_task
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        if cron_task is not None:
            cron_task.cancel()
        await ws_manager.stop()
        if feishu_runner is not None:
            await feishu_runner.cleanup()
        await web_runner.cleanup()


async def _run_cron_ticker(home: Path) -> None:
    from agent.runtime import bootstrap, create_llm_call
    from cron.scheduler import CronScheduler, register_cron_scheduler

    base, settings = bootstrap(home)
    llm_call = create_llm_call(base, settings)
    scheduler = CronScheduler(home=base)
    register_cron_scheduler(scheduler, home=base, llm_call=llm_call, settings=settings)
    interval = float(settings.cron.tick_seconds)
    loop = asyncio.get_running_loop()
    while True:
        await loop.run_in_executor(None, scheduler.tick)
        await asyncio.sleep(interval)
