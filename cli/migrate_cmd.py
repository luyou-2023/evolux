"""CLI: migrate user data from Hermes Agent."""

from __future__ import annotations

import argparse
import sys

from cli.hermes_detect import discover_hermes_installs, format_detect_report, pick_default_source
from cli.hermes_migration import migrate_from_hermes
from evolux_constants import get_evolux_home


def add_migrate_parser(sub: argparse._SubParsersAction) -> None:
    migrate = sub.add_parser("migrate", help="Import data from other agents")
    migrate_sub = migrate.add_subparsers(dest="migrate_command")

    migrate_sub.add_parser("detect", help="Detect local Hermes installs and profiles")

    from_hermes = migrate_sub.add_parser("from-hermes", help="Migrate Hermes user sediment into Evolux")
    from_hermes.add_argument(
        "--source",
        help="Hermes home path (default: auto-detect ~/.hermes or $HERMES_HOME)",
    )
    from_hermes.add_argument(
        "--preset",
        choices=["user-data", "full"],
        default="user-data",
        help="user-data skips secrets; full merges ~/.hermes/.env",
    )
    from_hermes.add_argument("--overwrite", action="store_true", help="Overwrite conflicting files")
    from_hermes.add_argument("--dry-run", action="store_true", help="Preview migration only")
    from_hermes.add_argument("--yes", action="store_true", help="Skip confirmation prompt")


def _confirm(prompt: str) -> bool:
    try:
        answer = input(f"{prompt} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def run_migrate(args: argparse.Namespace) -> int:
    if args.migrate_command == "detect":
        report = discover_hermes_installs()
        print(format_detect_report(report))
        return 0

    if args.migrate_command == "from-hermes":
        report = discover_hermes_installs()
        source = args.source
        if source:
            from pathlib import Path

            src_path = Path(source).expanduser()
        else:
            src_path = pick_default_source(report)
        if src_path is None:
            print("No Hermes install detected. Checked ~/.hermes, $HERMES_HOME, and profiles/.", file=sys.stderr)
            print("Run: evolux migrate detect", file=sys.stderr)
            return 1

        target = get_evolux_home()
        if not args.yes and not args.dry_run and sys.stdin.isatty():
            print(format_detect_report(report))
            print(f"\nWill migrate: {src_path} → {target} (preset={args.preset})")
            if not _confirm("Proceed?"):
                print("Cancelled.")
                return 1

        try:
            result = migrate_from_hermes(
                src_path,
                target,
                preset=args.preset,
                overwrite=bool(args.overwrite),
                dry_run=bool(args.dry_run),
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        for line in result.summary_lines():
            print(line)
        if not args.dry_run:
            print("\nNext:")
            print("  evolux skills reindex")
            print("  evolux chat")
        return 0

    print("usage: evolux migrate {detect|from-hermes}", file=sys.stderr)
    return 2
