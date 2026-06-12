"""Sub-agent description vector index."""

from __future__ import annotations

from pathlib import Path

from agent.agent_registry import AgentDefinition, AgentRegistry
from agent.session_monitor import is_internal_agent
from vector.embedder import Embedder, HashEmbedder
from vector.store import create_vector_store


class SubAgentIndex:
    def __init__(
        self,
        home: Path,
        registry: AgentRegistry | None = None,
        embedder: Embedder | None = None,
        *,
        backend: str = "sqlite-vec",
    ):
        self.home = home
        self.registry = registry or AgentRegistry(home=home)
        self.embedder = embedder or HashEmbedder()
        self.store = create_vector_store(home, "subagents.json", backend=backend)

    def sync_agent(self, agent: AgentDefinition) -> None:
        if agent.retired or is_internal_agent(agent.agent_id) or agent.stats.get("internal"):
            self.store.delete(agent.agent_id)
            return
        text = f"{agent.name} {agent.domain} {agent.description}"
        self.store.upsert(
            agent.agent_id,
            self.embedder.embed(text),
            {
                "agent_id": agent.agent_id,
                "assistant_id": agent.assistant_id,
                "name": agent.name,
                "domain": agent.domain,
                "description": agent.description,
                "skills": agent.skills,
            },
        )

    def search(self, query: str, *, assistant_id: str, top_k: int = 5) -> list[tuple[str, float, dict]]:
        return self.store.search(
            self.embedder.embed(query),
            top_k=top_k,
            metadata_filter={"assistant_id": assistant_id},
        )
