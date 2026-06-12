"""Default runtime configuration values."""

from __future__ import annotations

import os

DEFAULT_ORCHESTRATOR_MAX_ITERATIONS = 30
DEFAULT_SUBAGENT_MAX_ITERATIONS = 90


def orchestrator_max_iterations() -> int:
    raw = os.environ.get("EVOLUX_ORCHESTRATOR_MAX_ITERATIONS")
    return int(raw) if raw else DEFAULT_ORCHESTRATOR_MAX_ITERATIONS


def subagent_max_iterations() -> int:
    raw = os.environ.get("EVOLUX_SUBAGENT_MAX_ITERATIONS")
    return int(raw) if raw else DEFAULT_SUBAGENT_MAX_ITERATIONS
