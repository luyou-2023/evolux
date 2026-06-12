"""Evolux CLI entry point."""

from __future__ import annotations

import argparse
import sys

from cli.assistant import add_assistant_parser, run_assistant
from cli.chat import run_chat
from cli.dashboard_cmd import run_dashboard_start
from cli.gateway_cmd import run_gateway_start
from cli.setup import run_setup
from cli.tui import run_tui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evolux", description="Evolux multi-agent runtime")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Show version")
    sub.add_parser("setup", help="Initialize ~/.evolux config and directories")

    chat = sub.add_parser("chat", help="Interactive orchestrator chat")
    chat.add_argument("--assistant", default="default", help="Assistant id")

    sub.add_parser("tui", help="Terminal status UI")

    dashboard = sub.add_parser("dashboard", help="Web dashboard commands")
    dashboard_sub = dashboard.add_subparsers(dest="dashboard_command")
    dashboard_start = dashboard_sub.add_parser("start", help="Start dashboard HTTP server")
    dashboard_start.add_argument("--check", action="store_true", help="Validate config and exit")

    add_assistant_parser(sub)

    gateway = sub.add_parser("gateway", help="Gateway commands")
    gateway_sub = gateway.add_subparsers(dest="gateway_command")
    gateway_start = gateway_sub.add_parser("start", help="Start messaging gateway")
    gateway_start.add_argument("--check", action="store_true", help="Validate config and exit")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "version":
        print("evolux 0.3.0")
        return 0

    if args.command == "setup":
        return run_setup()

    if args.command == "chat":
        return run_chat(assistant_id=args.assistant)

    if args.command == "tui":
        return run_tui()

    if args.command == "dashboard":
        if args.dashboard_command == "start":
            if getattr(args, "check", False):
                return run_dashboard_start(foreground=False)
            return run_dashboard_start(foreground=True)
        parser.parse_args(["dashboard", "--help"])
        return 0

    if args.command == "assistant":
        if not args.assistant_command:
            parser.parse_args([*(argv or sys.argv[1:]), "--help"])
            return 0
        return run_assistant(args)

    if args.command == "gateway":
        if args.gateway_command == "start":
            if getattr(args, "check", False):
                return run_gateway_start(foreground=False)
            return run_gateway_start(foreground=True)
        parser.parse_args(["gateway", "--help"])
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
