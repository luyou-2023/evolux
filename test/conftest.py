"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from evolux_constants import EVOLUX_HOME_ENV, get_evolux_home
from evolux_env import load_env


@pytest.fixture(scope="session", autouse=True)
def _load_user_env():
    load_env(get_evolux_home())


@pytest.fixture
def evolux_home(tmp_path, monkeypatch):
    """Isolate EVOLUX_HOME to a temporary directory."""
    home = tmp_path / "evolux_home"
    home.mkdir()
    monkeypatch.setenv(EVOLUX_HOME_ENV, str(home))
    load_env(home)
    return home
