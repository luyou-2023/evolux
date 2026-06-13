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
    lines = [
        "## 路由预检（系统自动生成，供主控参考 — 由你决定是否委派）",
        "",
        "问答/解释类请求：优先用主控 LLM + 下方 Skill 直接回答。",
        "执行/MCP/多步任务：再考虑 dispatch 或 create 专家。",
        "",
    ]

    lines.append("### 识别到的 Skill（主控可 skill_view 或直接遵循已注入指令）")
    if ctx.skill_candidates:
        for idx, skill in enumerate(ctx.skill_candidates[:5], start=1):
            lines.append(f"{idx}. {skill.skill_name} ({skill.score:.2f}) — {skill.description}")
    else:
        lines.append("- （无匹配）")
    lines.append("")

    lines.append("### 已有专家（子 Agent，按需 dispatch）")
    if ctx.fused_ranking:
        for idx, item in enumerate(ctx.fused_ranking[:5], start=1):
            skills = ", ".join(item.skills) or "-"
            strength = "强匹配" if item.final_score >= 0.35 else "弱匹配"
            lines.append(
                f"{idx}. {item.agent_id} ({item.final_score:.2f}, {strength}) — skills: [{skills}]"
            )
    else:
        lines.append("- （尚无注册专家）")
    lines.append("")

    lines.append("### 协调提示（非强制）")
    if ctx.fused_ranking and ctx.fused_ranking[0].final_score >= 0.35:
        top = ctx.fused_ranking[0]
        lines.append(
            f"- 若需执行：可考虑 dispatch `{top.agent_id}`；若只是解释/讨论，请主控直接回答"
        )
    elif ctx.suggested_skills:
        lines.append(
            f"- 无强匹配专家；执行类任务可 create_subagent 并绑定 skills: "
            f"[{', '.join(ctx.suggested_skills[:3])}]"
        )
    else:
        lines.append("- 无强信号；按任务类型自行判断直接回复或委派")

    return "\n".join(lines)


def routing_decision_hints(ctx: RoutingContext, *, score_threshold: float = 0.35) -> list[str]:
    """Structured hints for orchestrator tools (LLM-readable, not prescriptive)."""
    hints: list[str] = []
    if ctx.fused_ranking and ctx.fused_ranking[0].final_score >= score_threshold:
        top = ctx.fused_ranking[0]
        hints.append(f"reuse_candidate: {top.agent_id} (score={top.final_score:.2f})")
    elif ctx.fused_ranking:
        hints.append("weak_expert_match: prefer orchestrator answer unless execution needed")
    else:
        hints.append("no_registered_expert: create_subagent only if execution-heavy and repeatable")
    if ctx.suggested_skills:
        hints.append(f"orchestrator_skills: {', '.join(ctx.suggested_skills[:5])}")
    code_experts = [
        item.agent_id
        for item in ctx.fused_ranking
        if "opencode" in item.agent_id.lower() or "code" in item.agent_id.lower()
    ]
    if code_experts:
        hints.append(
            f"code_task_hint: prefer MCP-bound expert (e.g. {code_experts[0]}) over bare terminal agents"
        )
    return hints
