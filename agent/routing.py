"""Triple-route fusion: Skill candidates + subagent vector scores."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SkillCandidate:
    skill_name: str
    score: float
    description: str = ""
    match_source: str = "keyword"


@dataclass
class SubAgentCandidate:
    agent_id: str
    vector_score: float
    name: str = ""
    domain: str = ""
    skills: list[str] = field(default_factory=list)
    recency_boost: float = 0.0


@dataclass
class FusionWeights:
    vector_weight: float = 0.5
    skill_overlap_weight: float = 0.4
    recency_weight: float = 0.1


@dataclass
class FusedCandidate:
    agent_id: str
    final_score: float
    vector_score: float
    skill_overlap: float
    recency_boost: float
    skills: list[str] = field(default_factory=list)


@dataclass
class RoutingContext:
    skill_candidates: list[SkillCandidate]
    subagent_candidates: list[SubAgentCandidate]
    fused_ranking: list[FusedCandidate]
    suggested_skills: list[str]
    prompt_block: str = ""


def skill_overlap(agent_skills: list[str], skill_candidates: list[SkillCandidate]) -> float:
    if not skill_candidates:
        return 0.0
    skill_names = {c.skill_name for c in skill_candidates}
    if not skill_names:
        return 0.0
    overlap = len(set(agent_skills) & skill_names)
    return overlap / len(skill_names)


def fuse_routing(
    skill_candidates: list[SkillCandidate],
    subagent_candidates: list[SubAgentCandidate],
    weights: FusionWeights | None = None,
) -> RoutingContext:
    w = weights or FusionWeights()
    fused: list[FusedCandidate] = []

    for agent in subagent_candidates:
        overlap = skill_overlap(agent.skills, skill_candidates)
        final = (
            w.vector_weight * agent.vector_score
            + w.skill_overlap_weight * overlap
            + w.recency_weight * agent.recency_boost
        )
        fused.append(
            FusedCandidate(
                agent_id=agent.agent_id,
                final_score=final,
                vector_score=agent.vector_score,
                skill_overlap=overlap,
                recency_boost=agent.recency_boost,
                skills=agent.skills,
            )
        )

    fused.sort(key=lambda item: item.final_score, reverse=True)
    suggested = [c.skill_name for c in sorted(skill_candidates, key=lambda x: x.score, reverse=True)]
    ctx = RoutingContext(
        skill_candidates=skill_candidates,
        subagent_candidates=subagent_candidates,
        fused_ranking=fused,
        suggested_skills=suggested,
    )
    ctx.prompt_block = format_routing_prompt(ctx)
    return ctx


def format_routing_prompt(ctx: RoutingContext) -> str:
    lines = ["## 路由预检（系统自动生成，供协调决策参考）", ""]

    lines.append("### 识别到的 Skill")
    if ctx.skill_candidates:
        for idx, skill in enumerate(ctx.skill_candidates[:5], start=1):
            lines.append(f"{idx}. {skill.skill_name} ({skill.score:.2f}) — {skill.description}")
    else:
        lines.append("- （无匹配）")
    lines.append("")

    lines.append("### 候选子 Agent（融合排序）")
    if ctx.fused_ranking:
        for idx, item in enumerate(ctx.fused_ranking[:5], start=1):
            skills = ", ".join(item.skills) or "-"
            lines.append(
                f"{idx}. {item.agent_id} ({item.final_score:.2f}) — skills: [{skills}]"
            )
    else:
        lines.append("- （无匹配）")
    lines.append("")

    if ctx.suggested_skills:
        lines.append("### 路由建议")
        top_agent = ctx.fused_ranking[0].agent_id if ctx.fused_ranking else None
        if top_agent:
            lines.append(
                f"- 优先委派 {top_agent}，预加载 skills: [{', '.join(ctx.suggested_skills[:3])}]"
            )
        else:
            lines.append(
                f"- 建议创建子 Agent，绑定 skills: [{', '.join(ctx.suggested_skills[:3])}]"
            )

    return "\n".join(lines)
