"""Evolux runtime paths and environment helpers."""

from __future__ import annotations

import os
from pathlib import Path

EVOLUX_HOME_ENV = "EVOLUX_HOME"
DEFAULT_HOME = Path.home() / ".evolux"


def get_evolux_home() -> Path:
    """Return the active Evolux data directory."""
    override = os.environ.get(EVOLUX_HOME_ENV)
    if override:
        return Path(override).expanduser()
    return DEFAULT_HOME
