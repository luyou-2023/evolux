"""Load secrets from ~/.evolux/.env into process environment."""

from __future__ import annotations

import os
from pathlib import Path

from evolux_constants import get_evolux_home


def load_env(home: Path | None = None) -> None:
    base = home or get_evolux_home()
    env_path = base / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
