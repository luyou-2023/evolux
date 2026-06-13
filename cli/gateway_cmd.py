"""Gateway CLI commands."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from agent.runtime import bootstrap, create_llm_call
from cli.gateway_service import (
    install_gateway_service,
    restart_gateway_service,
    run_gateway_background,
    start_gateway_service,
    status_gateway_service,
    stop_gateway_service,
    uninstall_gateway_service,
    validate_gateway_ready,
)
from evolux_logging import setup_logging
from gateway.assistant_registry import AssistantRegistry
from gateway.platforms.feishu import feishu_connection_mode, feishu_skips_evolux_transport
from gateway.platforms.feishu_hermes import (
    HERMES_DEFAULT_FEISHU_WEBHOOK_PATH,
    HERMES_DEFAULT_FEISHU_WEBHOOK_PORT,
    suggest_evolux_gateway_port,
)
from gateway.run import GatewayRunner
from gateway.webhook_server import run_webhook_server

logger = logging.getLogger("evolux.gateway")


def add_gateway_parser(sub: argparse._SubParsersAction) -> None:
    gateway = sub.add_parser("gateway", help="Gateway commands")
    gateway_sub = gateway.add_subparsers(dest="gateway_command")

    run = gateway_sub.add_parser("run", help="Run gateway in background (launchd/systemd)")
    run.add_argument("--check", action="store_true", help="Validate config and exit")
    run.add_argument(
        "--foreground",
        action="store_true",
        help="Run in foreground (blocks terminal; for debugging)",
    )

    start = gateway_sub.add_parser("start", help="Start installed gateway service (systemd/launchd)")
    install = gateway_sub.add_parser(
        "install",
        help="Install gateway user service (Linux systemd / macOS launchd)",
    )
    install.add_argument("--force", action="store_true", help="Reinstall service unit")
    gateway_sub.add_parser("uninstall", help="Remove gateway user service")
    gateway_sub.add_parser("stop", help="Stop installed gateway service")
    gateway_sub.add_parser("restart", help="Restart installed gateway service")
    gateway_sub.add_parser("status", help="Show gateway service status")


def _feishu_secret_for(registry: AssistantRegistry, assistant_id: str) -> str:
    assistant = registry.get(assistant_id)
    if not assistant:
        return ""
    feishu = assistant.platforms.get("feishu") or {}
    return str(feishu.get("verification_token") or feishu.get("app_secret") or "")


def run_gateway_foreground(home: Path | None = None, *, check_only: bool = False) -> int:
    base, settings = bootstrap(home)
    setup_logging(base)
    if validate_gateway_ready(base) != 0:
        return 1
    if check_only:
        print("Gateway configuration OK.")
        return 0

    registry = AssistantRegistry(home=base)
    feishu_assistants = [item for item in registry.list() if "feishu" in item.platforms]
    llm_call = create_llm_call(base, settings)
    runner = GatewayRunner(home=base, llm_call=llm_call)

    host = settings.gateway.host
    port = settings.gateway.port
    suggested = suggest_evolux_gateway_port(port)
    if suggested != port:
        print(
            f"Note: port {port} may conflict with Hermes; "
            f"consider gateway.port: {suggested} in config.yaml"
        )
    print(f"Starting Evolux gateway on http://{host}:{port}")
    print(f"Dashboard: http://{host}:{port}/dashboard")
    print(f"Cron ticker: every {settings.cron.tick_seconds}s")
    feishu_webhook_port = settings.gateway.feishu_webhook_port
    for item in feishu_assistants:
        cfg = item.platforms["feishu"]
        mode = feishu_connection_mode(cfg)
        if feishu_skips_evolux_transport(cfg):
            print(f"- {item.assistant_id}: Feishu via Hermes gateway (mode=shared_hermes)")
        elif mode == "websocket":
            print(f"- {item.assistant_id}: WebSocket long connection (no public URL required)")
        else:
            if feishu_webhook_port and feishu_webhook_port != port:
                base = f"http://{settings.gateway.feishu_webhook_host}:{feishu_webhook_port}"
                print(
                    f"- {item.assistant_id}: {base}{HERMES_DEFAULT_FEISHU_WEBHOOK_PATH} "
                    f"(Hermes-compatible webhook port)"
                )
                print(f"  alt: http://{host}:{port}/webhook/feishu/{item.assistant_id}")
            else:
                webhook = f"http://{host}:{port}/webhook/feishu/{item.assistant_id}"
                print(f"- {item.assistant_id}: {webhook} (mode=webhook)")

    async def _main() -> None:
        await run_webhook_server(
            runner,
            host=host,
            port=port,
            home=base,
            get_secret=lambda aid: _feishu_secret_for(registry, aid),
            registry=registry,
            feishu_webhook_host=settings.gateway.feishu_webhook_host,
            feishu_webhook_port=settings.gateway.feishu_webhook_port,
            hermes_compat=settings.gateway.hermes_compat,
        )

    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        logger.info("gateway stopped")
    return 0


def run_gateway(args: argparse.Namespace, home: Path | None = None) -> int:
    cmd = args.gateway_command
    if cmd == "run":
        if bool(getattr(args, "check", False)):
            return run_gateway_foreground(home, check_only=True)
        if bool(getattr(args, "foreground", False)):
            return run_gateway_foreground(home, check_only=False)
        return run_gateway_background(home)
    if cmd == "start":
        return start_gateway_service()
    if cmd == "install":
        return install_gateway_service(home=home, force=bool(getattr(args, "force", False)))
    if cmd == "uninstall":
        return uninstall_gateway_service()
    if cmd == "stop":
        return stop_gateway_service()
    if cmd == "restart":
        return restart_gateway_service()
    if cmd == "status":
        return status_gateway_service()
    return 1


def run_gateway_start(home: Path | None = None, *, foreground: bool = True) -> int:
    """Backward-compatible alias used by older tests/callers."""
    if foreground:
        return run_gateway_foreground(home, check_only=False)
    base, _ = bootstrap(home)
    setup_logging(base)
    return validate_gateway_ready(base)
