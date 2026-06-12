"""ACP adapter entrypoint (Hermes-compatible)."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from evolux_constants import get_evolux_home
from evolux_env import load_env
from evolux_logging import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evolux-acp", description="Evolux ACP stdio server")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--setup", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print("evolux-acp 0.4.0")
        return 0
    if args.check:
        import acp  # noqa: F401
        from acp_adapter.server import EvoluxACPAgent  # noqa: F401
        from model_tools import get_tool_definitions

        tools = get_tool_definitions(platform="acp")
        print(f"Evolux ACP check OK ({len(tools)} tools)")
        return 0
    if args.setup:
        from cli.main import main as cli_main

        return cli_main(["setup"])

    home = get_evolux_home()
    load_env(home)
    setup_logging(home)
    logging.getLogger(__name__).info("Starting Evolux ACP adapter")

    try:
        import acp
        from acp_adapter.server import EvoluxACPAgent
    except ImportError:
        print(
            "Install ACP dependencies: pip install evolux[acp]",
            file=sys.stderr,
        )
        return 1

    agent = EvoluxACPAgent()
    try:
        asyncio.run(acp.run_agent(agent, use_unstable_protocol=True))
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
