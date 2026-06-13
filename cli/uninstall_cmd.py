"""CLI: uninstall Evolux (Hermes-compatible keep-data vs full wipe)."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def add_uninstall_parser(sub: argparse._SubParsersAction) -> None:
    uninstall = sub.add_parser("uninstall", help="Remove Evolux install (keep or wipe user data)")
    uninstall.add_argument(
        "--keep-data",
        action="store_true",
        help="Remove code/wrapper only; keep ~/.evolux",
    )
    uninstall.add_argument(
        "--full",
        action="store_true",
        help="Remove ~/.evolux data directory as well",
    )
    uninstall.add_argument("--yes", action="store_true", help="Skip confirmation prompt")


def _confirm(prompt: str) -> bool:
    try:
        answer = input(f"{prompt} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def _shell_configs() -> list[Path]:
    home = Path.home()
    return [path for path in (home / ".zshrc", home / ".zprofile", home / ".bashrc", home / ".profile") if path.exists()]


def _strip_path_entries() -> list[Path]:
    updated: list[Path] = []
    for config in _shell_configs():
        lines = config.read_text(encoding="utf-8").splitlines()
        new_lines: list[str] = []
        skip_next = False
        for line in lines:
            if "# Evolux" in line or "# evolux" in line.lower():
                skip_next = True
                continue
            if skip_next and "evolux" in line.lower() and "PATH" in line:
                skip_next = False
                continue
            skip_next = False
            if "evolux" in line.lower() and "PATH" in line:
                continue
            new_lines.append(line)
        content = "\n".join(new_lines)
        while "\n\n\n" in content:
            content = content.replace("\n\n\n", "\n\n")
        if content != config.read_text(encoding="utf-8"):
            config.write_text(content, encoding="utf-8")
            updated.append(config)
    return updated


def _remove_wrappers() -> list[Path]:
    removed: list[Path] = []
    for wrapper in (Path.home() / ".local" / "bin" / "evolux", Path("/usr/local/bin/evolux")):
        if not wrapper.exists():
            continue
        try:
            content = wrapper.read_text(encoding="utf-8")
        except OSError:
            content = ""
        if wrapper.is_symlink() or "evolux" in content.lower() or "cli.main" in content:
            wrapper.unlink(missing_ok=True)
            removed.append(wrapper)
    return removed


def _remove_install_dir() -> Path | None:
    candidates = [
        Path.home() / ".evolux" / "evolux",
        Path.home() / ".local" / "share" / "evolux",
        Path("/usr/local/lib/evolux"),
    ]
    for path in candidates:
        if path.is_dir() and (path / "pyproject.toml").exists():
            shutil.rmtree(path)
            return path
    return None


def run_uninstall(args: argparse.Namespace, *, home: Path | None = None) -> int:
    from evolux_constants import get_evolux_home

    data_home = home or get_evolux_home()
    keep_data = bool(args.keep_data)
    full_wipe = bool(args.full)
    if not keep_data and not full_wipe and sys.stdin.isatty() and not args.yes:
        print("Choose uninstall mode:")
        print("  1) keep data — remove wrapper/code only (default)")
        print("  2) full — also delete EVOLUX_HOME")
        choice = input("Selection [1/2]: ").strip()
        full_wipe = choice == "2"
        keep_data = not full_wipe
    elif full_wipe:
        keep_data = False

    if not args.yes and sys.stdin.isatty():
        mode = "full wipe" if full_wipe else "keep data"
        if not _confirm(f"Uninstall Evolux ({mode})?"):
            print("Cancelled.")
            return 1

    removed_wrappers = _remove_wrappers()
    updated_shell = _strip_path_entries()
    install_dir = _remove_install_dir()

    if full_wipe and data_home.exists():
        shutil.rmtree(data_home)

    print("Evolux uninstall complete.")
    if removed_wrappers:
        print("  removed wrapper:", ", ".join(str(p) for p in removed_wrappers))
    if updated_shell:
        print("  updated shell config:", ", ".join(str(p) for p in updated_shell))
    if install_dir:
        print(f"  removed install dir: {install_dir}")
    if keep_data:
        print(f"  kept user data: {data_home}")
    elif full_wipe:
        print(f"  removed user data: {data_home}")
    return 0
