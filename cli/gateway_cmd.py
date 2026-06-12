"""Gateway CLI commands."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from agent.runtime import bootstrap, create_llm_call
from evolux_constants import get_evolux_home
from evolux_logging import setup_logging
from gateway.assistant_registry import AssistantRegistry
from gateway.run import GatewayRunner
from gateway.webhook_server import AIOHTTP_AVAILABLE, run_webhook_server

logger = logging.getLogger("evolux.gateway")


def _feishu_secret_for(registry: AssistantRegistry, assistant_id: str) -> str:
    assistant = registry.get(assistant_id)
    if not assistant:
        return ""
    feishu = assistant.platforms.get("feishu") or {}
    return str(feishu.get("verification_token") or feishu.get("app_secret") or "")


def run_gateway_start(home: Path | None = None, *, foreground: bool = True) -> int:
    base, settings = bootstrap(home)
    setup_logging(base)

    registry = AssistantRegistry(home=base)
    feishu_assistants = [item for item in registry.list() if "feishu" in item.platforms]
    if not feishu_assistants:
        print("No Feishu assistants configured.")
        print("Run: evolux assistant bind feishu --id work-bot --app-id <id> --app-secret <secret>")
        return 1

    if not AIOHTTP_AVAILABLE:
        print("Install gateway dependencies: pip install evolux[gateway]")
        return 1

    llm_call = create_llm_call(base, settings)
    runner = GatewayRunner(home=base, llm_call=llm_call)

    host = settings.gateway.host
    port = settings.gateway.port
    print(f"Starting Evolux gateway on http://{host}:{port}")
    for item in feishu_assistants:
        cfg = item.platforms["feishu"]
        webhook = f"http://{host}:{port}/webhook/feishu/{item.assistant_id}"
        print(f"- {item.assistant_id}: {webhook} (mode={cfg.get('mode', 'webhook')})")

    if not foreground:
        return 0

    async def _main() -> None:
        await run_webhook_server(
            runner,
            host=host,
            port=port,
            get_secret=lambda aid: _feishu_secret_for(registry, aid),
        )

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logger.info("gateway stopped")
    return 0
