"""Render TurnTrace for terminal output."""

from __future__ import annotations

import sys

from agent.turn_trace import TurnTrace, format_coordination_summary


def render_trace(trace: TurnTrace, *, stream=None) -> None:
    out = stream or sys.stderr
    if not _has_content(trace):
        return

    out.write("\n── Evolux 协调过程 ──\n")
    for line in format_coordination_summary(trace):
        out.write(f"  {line}\n")
    out.write("────────────────────\n")


def _has_content(trace: TurnTrace) -> bool:
    return bool(trace.routing_skills or trace.routing_agents or trace.steps)
