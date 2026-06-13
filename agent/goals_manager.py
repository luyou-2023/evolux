"""Persistent cross-session goals stored in GOALS.md."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from agent.memory_manager import MemoryManager


@dataclass
class Goal:
    goal_id: str
    text: str
    done: bool = False


_GOAL_LINE = re.compile(
    r"^- \[(?P<done>[ xX])\] id:(?P<goal_id>[\w-]+)\s+(?P<text>.+)$"
)


class GoalsManager:
    def __init__(self, home: Path | None = None, assistant_id: str = "default"):
        self.memory = MemoryManager(home=home, assistant_id=assistant_id)

    def _path(self) -> Path:
        return self.memory._memories_dir() / "GOALS.md"

    def list_goals(self) -> list[Goal]:
        path = self._path()
        if not path.exists():
            return []
        goals: list[Goal] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            match = _GOAL_LINE.match(line.strip())
            if not match:
                continue
            goals.append(
                Goal(
                    goal_id=match.group("goal_id"),
                    text=match.group("text").strip(),
                    done=match.group("done").lower() == "x",
                )
            )
        return goals

    def _write_goals(self, goals: list[Goal]) -> None:
        path = self._path()
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"- [{'x' if goal.done else ' '}] id:{goal.goal_id} {goal.text}" for goal in goals
        ]
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def add_goal(self, text: str) -> Goal:
        text = text.strip()
        if not text:
            raise ValueError("goal text is required")
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        goal = Goal(goal_id=f"goal-{uuid.uuid4().hex[:8]}", text=f"{text} (added {stamp})")
        goals = self.list_goals()
        goals.append(goal)
        self._write_goals(goals)
        return goal

    def mark_done(self, goal_id: str) -> bool:
        goals = self.list_goals()
        updated = False
        for goal in goals:
            if goal.goal_id == goal_id:
                goal.done = True
                updated = True
                break
        if updated:
            self._write_goals(goals)
        return updated

    def clear_done(self) -> int:
        goals = self.list_goals()
        remaining = [goal for goal in goals if not goal.done]
        removed = len(goals) - len(remaining)
        self._write_goals(remaining)
        return removed

    def read_snapshot(self, *, max_active: int = 8) -> str:
        goals = self.list_goals()
        active = [goal for goal in goals if not goal.done][:max_active]
        if not active:
            return ""
        lines = ["## 活跃目标（GOALS.md）", ""]
        for goal in active:
            lines.append(f"- [{goal.goal_id}] {goal.text}")
        return "\n".join(lines)
