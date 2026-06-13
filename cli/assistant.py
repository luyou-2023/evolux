"""Assistant management commands."""

from __future__ import annotations

import argparse
from pathlib import Path

from evolux_constants import get_evolux_home
from gateway.assistant_registry import AssistantRegistry


def add_assistant_parser(sub: argparse._SubParsersAction) -> None:
    assistant = sub.add_parser("assistant", help="Manage assistants")
    assistant_sub = assistant.add_subparsers(dest="assistant_command")

    assistant_sub.add_parser("list", help="List configured assistants")

    bind = assistant_sub.add_parser("bind", help="Bind a platform to an assistant")
    bind.add_argument("platform", choices=["feishu", "cli"])
    bind.add_argument("--id", default="default", help="Assistant id")
    bind.add_argument("--app-id", default="", help="Feishu app id")
    bind.add_argument("--app-secret", default="", help="Feishu app secret")
    bind.add_argument("--mode", default="websocket", choices=["webhook", "websocket", "shared_hermes"])


def run_assistant(args: argparse.Namespace, home: Path | None = None) -> int:
    base = home or get_evolux_home()
    registry = AssistantRegistry(home=base)

    if args.assistant_command == "list":
        for item in registry.list():
            platforms = ", ".join(item.platforms.keys()) or "-"
            print(f"{item.assistant_id}\t{item.name}\t[{platforms}]")
        return 0

    if args.assistant_command == "bind":
        if args.platform == "feishu":
            registry.bind_platform(
                args.id,
                "feishu",
                {
                    "app_id": args.app_id,
                    "app_secret": args.app_secret,
                    "mode": args.mode,
                },
            )
        else:
            registry.bind_platform(args.id, "cli", {})
        print(f"Bound {args.platform} -> assistant {args.id}")
        return 0

    return 1
