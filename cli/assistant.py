"""Assistant management commands."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cli.feishu_setup import (
    feishu_register_app_available,
    print_feishu_setup_success,
    resolve_feishu_bind_mode,
    run_feishu_app_wizard,
)
from evolux_constants import get_evolux_home
from gateway.assistant_registry import AssistantRegistry


def add_assistant_parser(sub: argparse._SubParsersAction) -> None:
    assistant = sub.add_parser("assistant", help="Manage assistants")
    assistant_sub = assistant.add_subparsers(dest="assistant_command")

    assistant_sub.add_parser("list", help="List configured assistants")

    create = assistant_sub.add_parser("create", help="Create a new assistant")
    create.add_argument("--id", required=True, help="Assistant id")
    create.add_argument("--name", default="", help="Display name")

    bind = assistant_sub.add_parser("bind", help="Bind a platform to an assistant")
    bind.add_argument("platform", choices=["feishu", "cli"])
    bind.add_argument("--id", default="default", help="Assistant id")
    bind.add_argument("--app-id", default="", help="Feishu app id")
    bind.add_argument("--app-secret", default="", help="Feishu app secret")
    bind.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "webhook", "websocket", "shared_hermes"],
        help="Feishu mode (auto: shared_hermes when Hermes gateway runs)",
    )
    bind.add_argument(
        "--wizard",
        action="store_true",
        help="Create Feishu app via scan/URL (official register_app)",
    )
    bind.add_argument("--app-name", default="", help="Preset Feishu app name (wizard)")
    bind.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open authorization URL in browser (wizard)",
    )


def run_assistant(args: argparse.Namespace, home: Path | None = None) -> int:
    base = home or get_evolux_home()
    registry = AssistantRegistry(home=base)

    if args.assistant_command == "list":
        for item in registry.list():
            platforms = ", ".join(item.platforms.keys()) or "-"
            print(f"{item.assistant_id}\t{item.name}\t[{platforms}]")
        return 0

    if args.assistant_command == "create":
        registry.ensure_assistant(args.id, name=args.name or None)
        print(f"Created assistant {args.id}")
        return 0

    if args.assistant_command == "bind":
        if args.platform == "feishu":
            use_wizard = args.wizard or (not args.app_id and not args.app_secret)
            if use_wizard:
                if not feishu_register_app_available():
                    print(
                        "Feishu wizard requires: pip install 'evolux[gateway]' (lark-oapi>=1.5.5)",
                        file=sys.stderr,
                    )
                    return 1
                registry.ensure_assistant(args.id)
                try:
                    result = run_feishu_app_wizard(
                        registry,
                        assistant_id=args.id,
                        app_name=args.app_name or None,
                        mode=args.mode,
                        open_browser=not args.no_browser,
                    )
                except KeyboardInterrupt:
                    print("\nCancelled.", file=sys.stderr)
                    return 130
                except Exception as exc:
                    print(f"Feishu wizard failed: {exc}", file=sys.stderr)
                    return 1
                print_feishu_setup_success(result, home=base)
                return 0

            if not args.app_id or not args.app_secret:
                print(
                    "Provide --app-id and --app-secret, or run:\n"
                    "  evolux assistant bind feishu --wizard\n"
                    "  evolux feishu setup",
                    file=sys.stderr,
                )
                return 1

            mode = resolve_feishu_bind_mode(requested=args.mode, home=base)
            registry.bind_platform(
                args.id,
                "feishu",
                {
                    "app_id": args.app_id,
                    "app_secret": args.app_secret,
                    "mode": mode,
                },
            )
        else:
            registry.bind_platform(args.id, "cli", {})
        print(f"Bound {args.platform} -> assistant {args.id}")
        return 0

    return 1
