"""Evolux runtime paths and environment helpers."""

from __future__ import annotations

import os
from pathlib import Path

EVOLUX_HOME_ENV = "EVOLUX_HOME"
EVOLUX_PROFILE_ENV = "EVOLUX_PROFILE"
DEFAULT_HOME = Path.home() / ".evolux"


def get_evolux_home() -> Path:
    """Return the active Evolux data directory."""
    override = os.environ.get(EVOLUX_HOME_ENV)
    if override:
        return Path(override).expanduser()
    profile = os.environ.get(EVOLUX_PROFILE_ENV, "").strip()
    if profile:
        return DEFAULT_HOME / "profiles" / profile
    return DEFAULT_HOME


def apply_profile(profile: str | None) -> None:
    """Set EVOLUX_PROFILE for the current process (Hermes -p compatible)."""
    if profile:
        os.environ[EVOLUX_PROFILE_ENV] = profile
    elif EVOLUX_PROFILE_ENV in os.environ:
        del os.environ[EVOLUX_PROFILE_ENV]
