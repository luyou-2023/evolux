"""Persist orchestrator plan_task output per session for next-turn injection."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from agent.planning_state import format_plan_block
from evolux_constants import get_evolux_home


def _plan_path(home: Path, session_key: str) -> Path:
    digest = hashlib.sha256(session_key.encode("utf-8")).hexdigest()[:16]
    return home / "state" / "plans" / f"{digest}.json"


def save_session_plan(
    home: Path,
    session_key: str,
    *,
    goal: str,
    steps: list[dict[str, Any]],
) -> None:
    path = _plan_path(home, session_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"goal": goal, "steps": steps}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_session_plan(home: Path | None, session_key: str) -> str:
    base = home or get_evolux_home()
    path = _plan_path(base, session_key)
    if not path.exists():
        return ""
    raw = json.loads(path.read_text(encoding="utf-8"))
    goal = str(raw.get("goal") or "")
    steps = raw.get("steps") or []
    if not goal and not steps:
        return ""
    return format_plan_block(goal, steps)


def clear_session_plan(home: Path, session_key: str) -> None:
    path = _plan_path(home, session_key)
    if path.exists():
        path.unlink()
