"""Skill identification for triple-route preflight."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from agent.routing import SkillCandidate
from vector.embedder import Embedder, HashEmbedder
from vector.skill_index import SkillIndex, SkillRecord


@dataclass
class SkillMeta:
    skill_name: str
    description: str
    path: Path
    domain_tags: list[str] | None = None


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


class SkillRouter:
    def __init__(self, home: Path, embedder: Embedder | None = None, *, backend: str = "json"):
        self.home = home
        self.skills_dir = home / "skills"
        embedder = embedder or HashEmbedder()
        self.index = SkillIndex(home, embedder=embedder, backend=backend)
        self.embedder = embedder

    def scan_skills(self) -> list[SkillMeta]:
        if not self.skills_dir.exists():
            return []
        found: list[SkillMeta] = []
        for skill_md in self.skills_dir.glob("*/SKILL.md"):
            meta = parse_skill_md(skill_md)
            if meta:
                found.append(meta)
                self.index.upsert(
                    SkillRecord(
                        skill_name=meta.skill_name,
                        description=meta.description,
                        path=str(meta.path),
                        domain_tags=meta.domain_tags,
                    )
                )
        return found

    def identify(
        self,
        query: str,
        *,
        top_k: int = 5,
        allowlist: list[str] | None = None,
        enable_keyword: bool = True,
        enable_vector: bool = True,
    ) -> list[SkillCandidate]:
        skills = self.scan_skills()
        if allowlist:
            allow = set(allowlist)
            skills = [s for s in skills if s.skill_name in allow]

        candidates: dict[str, SkillCandidate] = {}

        if enable_keyword:
            query_lower = query.lower()
            for skill in skills:
                haystack = f"{skill.skill_name} {skill.description}".lower()
                if any(token in haystack for token in query_lower.split() if len(token) > 2):
                    candidates[skill.skill_name] = SkillCandidate(
                        skill_name=skill.skill_name,
                        score=0.75,
                        description=skill.description,
                        match_source="keyword",
                    )

        if enable_vector:
            for skill_name, score, meta in self.index.search(query, top_k=top_k):
                if allowlist and skill_name not in set(allowlist):
                    continue
                prev = candidates.get(skill_name)
                if prev is None or score > prev.score:
                    candidates[skill_name] = SkillCandidate(
                        skill_name=skill_name,
                        score=float(score),
                        description=meta.get("description", ""),
                        match_source="vector",
                    )

        ranked = sorted(candidates.values(), key=lambda c: c.score, reverse=True)
        return ranked[:top_k]

    def load_for_execution(self, skill_names: list[str]) -> str:
        chunks: list[str] = []
        for name in skill_names:
            path = self.skills_dir / name / "SKILL.md"
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            body = _strip_frontmatter(text)
            chunks.append(f"### Skill: {name}\n{body.strip()}")
        return "\n\n".join(chunks)


def parse_skill_md(path: Path) -> SkillMeta | None:
    text = path.read_text(encoding="utf-8")
    name = path.parent.name
    description = ""
    domain_tags: list[str] = []

    match = _FRONTMATTER_RE.match(text)
    if match:
        frontmatter = match.group(1)
        for line in frontmatter.splitlines():
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip()

    if not description:
        body = _strip_frontmatter(text)
        description = body.strip().splitlines()[0][:200] if body.strip() else name

    return SkillMeta(skill_name=name, description=description, path=path, domain_tags=domain_tags)


def _strip_frontmatter(text: str) -> str:
    match = _FRONTMATTER_RE.match(text)
    if match:
        return text[match.end() :]
    return text
