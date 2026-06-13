"""Helpers for spawning MCP stdio subprocesses safely."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_EVOLUX_REPO_ROOT = Path(__file__).resolve().parents[1]


def _looks_like_evolux_package_root(path: Path) -> bool:
    return (path / "mcp" / "stdio_client.py").is_file() and (path / "agent" / "runtime.py").is_file()


def sanitize_subprocess_env(
    env: dict[str, str],
    *,
    evolux_home: Path | None = None,
) -> dict[str, str]:
    """Drop PYTHONPATH entries that would shadow the official MCP SDK with Evolux's ``mcp`` package."""
    sanitized = dict(env)
    pythonpath = sanitized.get("PYTHONPATH")
    if not pythonpath:
        return sanitized

    blocked: set[str] = {str(_EVOLUX_REPO_ROOT.resolve())}
    if evolux_home is not None:
        blocked.add(str(evolux_home.expanduser().resolve()))

    kept: list[str] = []
    for part in pythonpath.split(os.pathsep):
        if not part:
            continue
        try:
            resolved = str(Path(part).expanduser().resolve())
        except OSError:
            kept.append(part)
            continue
        if resolved in blocked or _looks_like_evolux_package_root(Path(resolved)):
            continue
        kept.append(part)

    if kept:
        sanitized["PYTHONPATH"] = os.pathsep.join(kept)
    else:
        sanitized.pop("PYTHONPATH", None)
    return sanitized


def build_stdio_env(user_env: dict[str, Any] | None, *, evolux_home: Path | None = None) -> dict[str, str]:
    """Merge baseline process env with per-server overrides."""
    env = os.environ.copy()
    if user_env:
        for key, value in user_env.items():
            env[str(key)] = str(value)
    return sanitize_subprocess_env(env, evolux_home=evolux_home)


def resolve_stdio_cwd(config: dict[str, Any], command: str, args: list[str]) -> str | None:
    """Resolve working directory for an MCP stdio server."""
    raw_cwd = config.get("cwd")
    if raw_cwd not in (None, ""):
        return str(Path(str(raw_cwd)).expanduser())

    for candidate in [command, *args]:
        text = str(candidate).strip()
        if not text:
            continue
        path = Path(text).expanduser()
        if path.suffix == ".py" and path.is_file():
            return str(path.parent.resolve())
        if path.is_file():
            return str(path.parent.resolve())
    return None


def resolve_stdio_timeout(config: dict[str, Any], *, default: float = 120.0) -> float:
    raw = config.get("timeout", default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def resolve_stdio_connect_timeout(config: dict[str, Any], *, default: float = 60.0) -> float:
    raw = config.get("connect_timeout", default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default
