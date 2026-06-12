"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from evolux_constants import EVOLUX_HOME_ENV


@pytest.fixture
def evolux_home(tmp_path, monkeypatch):
    """Isolate EVOLUX_HOME to a temporary directory."""
    home = tmp_path / "evolux_home"
    home.mkdir()
    monkeypatch.setenv(EVOLUX_HOME_ENV, str(home))
    return home
