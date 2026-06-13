"""Evolux CLI entry point."""

from __future__ import annotations

import argparse
import sys

from cli.acp_cmd import run_acp_start
from cli.assistant import add_assistant_parser, run_assistant
from cli.chat import run_chat, run_chat_once
from cli.completion import run_completion
from cli.cron_cmd import add_cron_parser, run_cron
from cli.dashboard_cmd import run_dashboard_start
from cli.gateway_cmd import add_gateway_parser, run_gateway
from cli.migrate_cmd import add_migrate_parser, run_migrate
from cli.setup import run_setup
from cli.skills_cmd import add_skills_parser, run_skills
from cli.tui import run_tui
from cli.uninstall_cmd import add_uninstall_parser, run_uninstall
from evolux_constants import apply_profile


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evolux", description="Evolux multi-agent runtime")
    parser.add_argument(
        "-p",
        "--profile",
        help="Use isolated profile under ~/.evolux/profiles/<name> (Hermes-compatible)",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("version", help="Show version")
    setup = sub.add_parser("setup", help="Initialize ~/.evolux config and directories")
    setup.add_argument(
        "--from-hermes",
        action="store_true",
        help="Auto-import Hermes sediment when detected",
    )
    setup.add_argument("--skip-hermes", action="store_true", help="Do not offer Hermes migration")
    setup.add_argument(
        "--preset",
        choices=["user-data", "full"],
        default="user-data",
        help="Hermes migration preset when importing",
    )
    setup.add_argument("--yes", action="store_true", help="Skip Hermes migration prompt")

    chat = sub.add_parser("chat", help="Interactive orchestrator chat")
    chat.add_argument("--assistant", default="default", help="Assistant id")
    chat.add_argument("--once", metavar="MESSAGE", help="Run a single turn and print the reply")
    chat.add_argument(
        "--trace",
        action="store_true",
        help="Show orchestration trace (tools/MCP/subagents) on stderr",
    )

    completion = sub.add_parser("completion", help="Shell completion scripts")
    completion.add_argument("shell", choices=["zsh", "bash"], help="Shell name")

    sub.add_parser("tui", help="Terminal status UI")

    add_skills_parser(sub)
    add_cron_parser(sub)

    acp = sub.add_parser("acp", help="Editor ACP adapter (Hermes-compatible)")
    acp_sub = acp.add_subparsers(dest="acp_command")
    acp_start = acp_sub.add_parser("start", help="Start ACP adapter or validate wiring")
    acp_start.add_argument("--check", action="store_true", help="Validate ACP tool wiring only")

    dashboard = sub.add_parser("dashboard", help="Web dashboard commands")
    dashboard_sub = dashboard.add_subparsers(dest="dashboard_command")
    dashboard_start = dashboard_sub.add_parser("start", help="Start dashboard HTTP server")
    dashboard_start.add_argument("--check", action="store_true", help="Validate config and exit")

    add_assistant_parser(sub)
    add_migrate_parser(sub)
    add_uninstall_parser(sub)
    add_gateway_parser(sub)

    return parser


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv if argv is not None else sys.argv[1:])
    profile = None
    cleaned: list[str] = []
    idx = 0
    while idx < len(raw_argv):
        token = raw_argv[idx]
        if token in {"-p", "--profile"} and idx + 1 < len(raw_argv):
            profile = raw_argv[idx + 1]
            idx += 2
            continue
        cleaned.append(token)
        idx += 1
    apply_profile(profile)

    parser = build_parser()
    args = parser.parse_args(cleaned)

    if args.command == "version":
        print("evolux 0.4.0")
        return 0

    if args.command == "setup":
        return run_setup(
            from_hermes=bool(getattr(args, "from_hermes", False)),
            skip_hermes=bool(getattr(args, "skip_hermes", False)),
            hermes_preset=str(getattr(args, "preset", "user-data")),
            yes=bool(getattr(args, "yes", False)),
        )

    if args.command == "chat":
        trace = bool(getattr(args, "trace", False))
        if getattr(args, "once", None):
            return run_chat_once(args.once, assistant_id=args.assistant, trace=trace)
        return run_chat(assistant_id=args.assistant, trace=trace)

    if args.command == "completion":
        return run_completion(args.shell)

    if args.command == "tui":
        return run_tui()

    if args.command == "skills":
        if not args.skills_command:
            parser.parse_args(["skills", "--help"])
            return 0
        return run_skills(args)

    if args.command == "cron":
        if not args.cron_command:
            parser.parse_args(["cron", "--help"])
            return 0
        return run_cron(args)

    if args.command == "acp":
        if args.acp_command == "start":
            if getattr(args, "check", False):
                return run_acp_start(foreground=False)
            return run_acp_start(foreground=True)
        parser.parse_args(["acp", "--help"])
        return 0

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
        if not args.gateway_command:
            parser.parse_args(["gateway", "--help"])
            return 0
        return run_gateway(args)

    if args.command == "migrate":
        if not args.migrate_command:
            parser.parse_args(["migrate", "--help"])
            return 0
        return run_migrate(args)

    if args.command == "uninstall":
        return run_uninstall(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
