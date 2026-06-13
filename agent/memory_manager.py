"""Frozen MEMORY/USER snapshot loader."""

from __future__ import annotations

from pathlib import Path

from evolux_constants import get_evolux_home

ENTRY_DELIMITER = "\n§\n"


class MemoryManager:
    def __init__(self, home: Path | None = None, assistant_id: str = "default"):
        self.home = home or get_evolux_home()
        self.assistant_id = assistant_id

    def _memories_dir(self) -> Path:
        if self.assistant_id == "default":
            return self.home / "memories"
        return self.home / "assistants" / self.assistant_id / "memories"

    def read_snapshot(self) -> str:
        parts: list[str] = []
        for name in ("USER.md", "MEMORY.md"):
            path = self._memories_dir() / name
            if path.exists():
                parts.append(f"<!-- {name} -->\n{path.read_text(encoding='utf-8').strip()}")
        return "\n\n".join(parts)

    def agent_memory_path(self, agent_id: str) -> Path:
        return self._memories_dir() / "agents" / agent_id / "MEMORY.md"

    def solutions_path(self) -> Path:
        return self._memories_dir() / "SOLUTIONS.md"

    def read_agent_memory(self, agent_id: str) -> str:
        path = self.agent_memory_path(agent_id)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").strip()

    def append_agent_memory(self, agent_id: str, entry: str) -> None:
        path = self.agent_memory_path(agent_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = self.read_agent_memory(agent_id)
        if existing:
            path.write_text(f"{existing}{ENTRY_DELIMITER}{entry.strip()}", encoding="utf-8")
        else:
            path.write_text(entry.strip(), encoding="utf-8")

    def append_solution(self, entry: str) -> None:
        path = self.solutions_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8").strip() if path.exists() else ""
        if existing:
            path.write_text(f"{existing}{ENTRY_DELIMITER}{entry.strip()}", encoding="utf-8")
        else:
            path.write_text(entry.strip(), encoding="utf-8")

    def read_solutions_snapshot(self, *, max_chars: int = 4000) -> str:
        path = self.solutions_path()
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8").strip()
        if len(text) <= max_chars:
            return text
        return text[-max_chars:]

    def append_global_memory(self, entry: str) -> None:
        path = self._memories_dir() / "MEMORY.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8").strip() if path.exists() else ""
        if existing:
            path.write_text(f"{existing}{ENTRY_DELIMITER}{entry.strip()}", encoding="utf-8")
        else:
            path.write_text(entry.strip(), encoding="utf-8")

