"""Evolux CLI entry point."""

from __future__ import annotations

import argparse
import sys

from cli.assistant import add_assistant_parser, run_assistant
from cli.gateway_cmd import run_gateway_start
from cli.setup import run_setup


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evolux", description="Evolux multi-agent runtime")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Show version")
    sub.add_parser("setup", help="Initialize ~/.evolux config and directories")
    add_assistant_parser(sub)

    gateway = sub.add_parser("gateway", help="Gateway commands")
    gateway_sub = gateway.add_subparsers(dest="gateway_command")
    gateway_sub.add_parser("start", help="Start messaging gateway")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print("evolux 0.1.0")
        return 0

    if args.command == "setup":
        return run_setup()

    if args.command == "assistant":
        if not args.assistant_command:
            parser.parse_args([*(argv or sys.argv[1:]), "--help"])
            return 0
        return run_assistant(args)

    if args.command == "gateway":
        if args.gateway_command == "start":
            return run_gateway_start()
        parser.parse_args(["gateway", "--help"])
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
