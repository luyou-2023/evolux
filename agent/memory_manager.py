"""Frozen MEMORY/USER snapshot loader."""

from __future__ import annotations

from pathlib import Path

from evolux_constants import get_evolux_home


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
