"""Triple-route fusion: Skill candidates + subagent vector scores."""

from __future__ import annotations

import re
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
    user_message: str = ""


_EXEC_VERBS = ("运行", "执行", "run", "并运行", "跑一下", "运行结果", "给出运行")
_CODE_HINTS = ("python", "脚本", "hello", "代码", ".py", "写一个")


def looks_like_execution_task(text: str) -> bool:
    """True when the user expects code/scripts to be written or run (must dispatch)."""
    lower = (text or "").lower()
    has_exec = any(v in lower for v in _EXEC_VERBS)
    has_code = any(h in lower for h in _CODE_HINTS)
    if has_exec and has_code:
        return True
    if re.search(r"写.*(运行|run)", lower):
        return True
    return False


def routing_junk_penalty(agent_id: str) -> float:
    """Demote auto-created task-signature experts that pollute routing."""
    aid = agent_id or ""
    if "帮我把" in aid or "hermes-共用" in aid:
        return -0.6
    if aid.startswith("expert-") and len(aid) > 28:
        return -0.25
    return 0.0


def mcp_capability_boost(agent_id: str, *, has_mcp: bool, domain: str, execution_task: bool) -> float:
    if not execution_task:
        return 0.0
    boost = 0.0
    if has_mcp:
        boost += 0.45
    if (domain or "").lower() == "code":
        boost += 0.15
    if "code" in agent_id.lower() or "opencode" in agent_id.lower():
        boost += 0.1
    return boost


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
    *,
    user_message: str = "",
    agent_mcp: dict[str, bool] | None = None,
    agent_domains: dict[str, str] | None = None,
) -> RoutingContext:
    w = weights or FusionWeights()
    fused: list[FusedCandidate] = []
    execution_task = looks_like_execution_task(user_message)
    mcp_map = agent_mcp or {}
    domain_map = agent_domains or {}

    for agent in subagent_candidates:
        overlap = skill_overlap(agent.skills, skill_candidates)
        final = (
            w.vector_weight * agent.vector_score
            + w.skill_overlap_weight * overlap
            + w.recency_weight * agent.recency_boost
            + routing_junk_penalty(agent.agent_id)
            + mcp_capability_boost(
                agent.agent_id,
                has_mcp=mcp_map.get(agent.agent_id, False),
                domain=domain_map.get(agent.agent_id, agent.domain),
                execution_task=execution_task,
            )
        )
        final = max(0.0, final)
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
        user_message=user_message,
    )
    ctx.prompt_block = format_routing_prompt(ctx, execution_task=execution_task)
    return ctx


def format_routing_prompt(ctx: RoutingContext, *, execution_task: bool = False) -> str:
    lines = [
        "## 路由预检（系统自动生成，供主控参考 — 由你决定是否委派）",
        "",
        "问答/解释类请求：优先用主控 LLM + 下方 Skill 直接回答。",
        "执行/MCP/多步任务：必须 dispatch_subagent，禁止主控自行 terminal/write_file。",
        "",
    ]
    if execution_task:
        lines.extend(
            [
                "### ⚠️ 检测到执行任务（写代码/运行/要结果）",
                "- **必须** 调用 `dispatch_subagent` 交给有 MCP 的代码专家（如 code-dev-expert）",
                "- **禁止** 直接回复、禁止复用 SOLUTIONS/历史中的旧运行结果",
                "",
            ]
        )

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
        if execution_task:
            lines.append(f"- **必须 dispatch** `{top.agent_id}` 执行；主控只汇总专家返回")
        else:
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
    if looks_like_execution_task(ctx.user_message):
        hints.append("execution_task: MUST dispatch_subagent; do NOT answer from memory/SOLUTIONS")
    return hints


def execution_task_prompt_block() -> str:
    return (
        "## 强制执行委派\n"
        "用户请求包含写代码/运行/要结果 — 你必须调用 `dispatch_subagent`，"
        "不得直接回答，不得复用 SOLUTIONS 或会话中的旧运行结果。"
        "汇总时只引用专家返回的内容。"
    )
