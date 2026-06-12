"""Standalone dashboard HTTP server."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from agent.llm import MockLLMClient, llm_call_adapter
from agent.runtime import bootstrap
from evolux_logging import setup_logging
from gateway.run import GatewayRunner
from gateway.webhook_server import AIOHTTP_AVAILABLE, run_webhook_server

logger = logging.getLogger("evolux.dashboard")


def run_dashboard_start(home: Path | None = None, *, foreground: bool = True) -> int:
    base, settings = bootstrap(home)
    setup_logging(base)

    if not AIOHTTP_AVAILABLE:
        print("Install gateway dependencies: pip install evolux[gateway]")
        return 1

    host = settings.gateway.host
    port = settings.gateway.port
    print(f"Starting Evolux dashboard on http://{host}:{port}/dashboard")

    if not foreground:
        return 0

    mock = MockLLMClient(default_content="dashboard")
    runner = GatewayRunner(home=base, llm_call=llm_call_adapter(mock), send_feishu_reply=False)

    async def _main() -> None:
        await run_webhook_server(runner, host=host, port=port, home=base)

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logger.info("dashboard stopped")
    return 0
