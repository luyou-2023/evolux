"""Skill metadata vector index."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vector.embedder import Embedder, HashEmbedder
from vector.store import create_vector_store


@dataclass
class SkillRecord:
    skill_name: str
    description: str
    path: str = ""
    domain_tags: list[str] | None = None


class SkillIndex:
    def __init__(
        self,
        home: Path,
        embedder: Embedder | None = None,
        *,
        backend: str = "sqlite-vec",
    ):
        self.home = home
        self.embedder = embedder or HashEmbedder()
        self.store = create_vector_store(home, "skills.json", backend=backend)

    def upsert(self, record: SkillRecord) -> None:
        text = f"{record.skill_name} {record.description}"
        self.store.upsert(
            record.skill_name,
            self.embedder.embed(text),
            {
                "skill_name": record.skill_name,
                "description": record.description,
                "path": record.path,
                "domain_tags": record.domain_tags or [],
            },
        )

    def delete(self, skill_name: str) -> None:
        self.store.delete(skill_name)

    def search(self, query: str, *, top_k: int = 5) -> list[tuple[str, float, dict]]:
        return self.store.search(self.embedder.embed(query), top_k=top_k)
