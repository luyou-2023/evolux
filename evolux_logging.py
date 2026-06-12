"""Structured logging for Evolux processes."""

from __future__ import annotations

import logging
from pathlib import Path

from evolux_constants import get_evolux_home


def setup_logging(home: Path | None = None, *, level: int = logging.INFO) -> None:
    base = home or get_evolux_home()
    log_dir = base / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("evolux")
    if root.handlers:
        return

    root.setLevel(level)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)

    file_handler = logging.FileHandler(log_dir / "evolux.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
