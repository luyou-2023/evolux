"""ACP adapter entrypoint (Hermes-compatible CLI surface)."""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evolux-acp", description="Evolux ACP adapter")
    parser.add_argument("--version", action="store_true", help="Print version")
    parser.add_argument("--check", action="store_true", help="Validate ACP wiring")
    parser.add_argument("--setup", action="store_true", help="Run model/setup helper")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print("evolux-acp 0.4.0")
        return 0
    if args.check:
        from model_tools import get_tool_definitions

        tools = get_tool_definitions(platform="acp")
        print(f"Evolux ACP check OK ({len(tools)} tools)")
        return 0
    if args.setup:
        from cli.main import main as cli_main

        return cli_main(["setup"])
    print(
        "Evolux ACP adapter requires optional dependency `agent-client-protocol`.\n"
        "Run: pip install agent-client-protocol\n"
        "Then connect your editor to `evolux acp start`.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
