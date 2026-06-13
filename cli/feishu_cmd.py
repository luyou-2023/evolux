"""CLI: Feishu integration setup."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from cli.feishu_setup import (
    feishu_register_app_available,
    print_feishu_setup_success,
    run_feishu_app_wizard,
)
from evolux_constants import get_evolux_home
from gateway.assistant_registry import AssistantRegistry


def add_feishu_parser(sub: argparse._SubParsersAction) -> None:
    feishu = sub.add_parser("feishu", help="Feishu bot setup (scan / URL)")
    feishu_sub = feishu.add_subparsers(dest="feishu_command")

    setup = feishu_sub.add_parser(
        "setup",
        help="Create Feishu app via scan/URL and bind to an assistant",
    )
    setup.add_argument("--assistant", "--id", dest="assistant_id", default="default")
    setup.add_argument("--app-name", default="", help="Preset Feishu app name")
    setup.add_argument("--app-desc", default="", help="Preset Feishu app description")
    setup.add_argument(
        "--mode",
        default="auto",
        choices=["auto", "websocket", "webhook", "shared_hermes"],
        help="Connection mode (auto: shared_hermes when Hermes gateway runs)",
    )
    setup.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the authorization URL in a browser",
    )


def run_feishu(args: argparse.Namespace, home: Path | None = None) -> int:
    base = home or get_evolux_home()
    if args.feishu_command != "setup":
        print("Usage: evolux feishu setup [--assistant ID]", file=sys.stderr)
        return 1

    if not feishu_register_app_available():
        print(
            "Feishu scan setup requires gateway dependencies.\n"
            "  pip install 'evolux[gateway]'\n"
            "Or re-run install.sh after pulling latest Evolux.",
            file=sys.stderr,
        )
        return 1

    registry = AssistantRegistry(home=base)
    registry.ensure_assistant(args.assistant_id)

    try:
        result = run_feishu_app_wizard(
            registry,
            assistant_id=args.assistant_id,
            app_name=args.app_name or None,
            app_desc=args.app_desc or None,
            mode=args.mode,
            open_browser=not args.no_browser,
        )
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Feishu setup failed: {exc}", file=sys.stderr)
        return 1

    print_feishu_setup_success(result, home=base)
    return 0
