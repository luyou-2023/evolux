"""midscenejs_luke and expert installation commands."""

from __future__ import annotations

import argparse
import sys

from agent.agent_registry import AgentRegistry
from agent.expert_bootstrap import install_ui_automation_expert
from evolux_constants import get_evolux_home
from tools.midscene_luke_bridge import ensure_engine_deps, init_ui_test_project, luke_engine_root
from vector.subagent_index import SubAgentIndex


def add_expert_parser(sub: argparse._SubParsersAction) -> None:
    expert = sub.add_parser("expert", help="Install bundled domain experts")
    expert_sub = expert.add_subparsers(dest="expert_command")
    install = expert_sub.add_parser("install", help="Install an expert into agent registry")
    install.add_argument(
        "name",
        choices=["ui-automation"],
        help="Expert template name",
    )
    install.add_argument("--assistant", default="default", help="Assistant id")
    install.add_argument("--replace", action="store_true", help="Overwrite existing expert")


def add_midscene_parser(sub: argparse._SubParsersAction) -> None:
    mid = sub.add_parser("midscene", help="midscenejs_luke UI automation engine")
    mid_sub = mid.add_subparsers(dest="midscene_command")
    mid_sub.add_parser("status", help="Check engine deps")
    init = mid_sub.add_parser("init", help="Install npm deps + scaffold ui-tests")
    init.add_argument("--skip-npm", action="store_true", help="Skip npm install in engine")


def run_expert(args: argparse.Namespace) -> int:
    home = get_evolux_home()
    registry = AgentRegistry(home=home)
    index = SubAgentIndex(home, registry=registry)

    if args.expert_command == "install":
        if args.name == "ui-automation":
            agent = install_ui_automation_expert(
                registry,
                index,
                assistant_id=args.assistant,
                replace=bool(args.replace),
            )
            print(f"Installed expert: {agent.agent_id} (assistant={args.assistant})")
            print(f"  toolsets: {agent.toolsets}")
            print(f"  skills: {agent.skills}")
            return 0
    return 1


def run_midscene(args: argparse.Namespace) -> int:
    root = luke_engine_root()
    if args.midscene_command == "status":
        ok, detail = ensure_engine_deps(root)
        print(f"midscenejs_luke: {'ready' if ok else 'not ready'}")
        print(f"  root: {root}")
        print(f"  detail: {detail}")
        return 0 if ok else 1

    if args.midscene_command == "init":
        if not args.skip_npm:
            ok, detail = ensure_engine_deps(root)
            if not ok:
                print(f"npm install failed: {detail}", file=sys.stderr)
                return 1
        workspace = init_ui_test_project()
        print(f"UI test workspace: {workspace}")
        print("Set MIDSCENE_LUKE_MODEL_* env vars, then: evolux expert install ui-automation")
        return 0

    return 1
