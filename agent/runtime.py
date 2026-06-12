"""Build runtime components from settings."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from agent.llm import create_llm_client, llm_call_adapter
from agent.settings import Settings, load_settings
from evolux_constants import get_evolux_home
from evolux_env import load_env


def bootstrap(home: Path | None = None) -> tuple[Path, Settings]:
    base = home or get_evolux_home()
    load_env(base)
    return base, load_settings(base)


def create_llm_call(home: Path | None = None, settings: Settings | None = None) -> Callable:
    base = home or get_evolux_home()
    load_env(base)
    cfg = settings or load_settings(base)
    client = create_llm_client(
        model=cfg.llm.model,
        base_url=cfg.llm.base_url,
        api_key=cfg.llm.api_key,
    )
    return llm_call_adapter(client)
