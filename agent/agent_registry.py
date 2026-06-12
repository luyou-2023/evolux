"""Persistent registry of domain expert sub-agents."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evolux_constants import get_evolux_home


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentDefinition:
    agent_id: str
    assistant_id: str
    name: str
    domain: str
    description: str
    system_prompt_template: str = ""
    toolsets: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)
    retired: bool = False
    stats: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentDefinition:
        return cls(**data)


class AgentRegistry:
    """JSON-backed store of sub-agent definitions."""

    def __init__(self, home: Path | None = None):
        self.home = home or get_evolux_home()
        self.path = self.home / "agents" / "registry.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, data: dict[str, dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def register(self, agent: AgentDefinition) -> None:
        data = self._read()
        payload = asdict(agent)
        payload["updated_at"] = _utc_now()
        data[agent.agent_id] = payload
        self._write(data)

    def get(self, agent_id: str, *, include_retired: bool = False) -> AgentDefinition | None:
        raw = self._read().get(agent_id)
        if raw is None:
            return None
        agent = AgentDefinition.from_dict(raw)
        if agent.retired and not include_retired:
            return None
        return agent

    def list_by_assistant(self, assistant_id: str) -> list[AgentDefinition]:
        agents = []
        for raw in self._read().values():
            agent = AgentDefinition.from_dict(raw)
            if agent.assistant_id == assistant_id and not agent.retired:
                agents.append(agent)
        return sorted(agents, key=lambda a: a.agent_id)

    def retire(self, agent_id: str) -> None:
        data = self._read()
        if agent_id not in data:
            return
        data[agent_id]["retired"] = True
        data[agent_id]["updated_at"] = _utc_now()
        self._write(data)
