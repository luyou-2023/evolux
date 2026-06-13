"""Repeat-task detection and automatic expert sub-agent promotion."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.agent_registry import AgentDefinition, AgentRegistry
from agent.routing import RoutingContext
from agent.sedimentation import build_default_system_prompt, default_toolsets_for_domain
from agent.settings import ExpertPromotionSettings
from evolux_constants import get_evolux_home
from vector.subagent_index import SubAgentIndex

_SIGNATURE_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "please",
        "help",
        "me",
        "my",
        "with",
        "for",
        "to",
        "and",
        "or",
        "请",
        "帮",
        "我",
        "一下",
    }
)


def normalize_task_signature(text: str) -> str:
    tokens = re.findall(r"[\w\u4e00-\u9fff]+", (text or "").lower())
    filtered = [token for token in tokens if token not in _SIGNATURE_STOPWORDS and len(token) > 1]
    if not filtered:
        filtered = tokens[:6]
    return " ".join(filtered[:8])


def infer_domain(user_message: str, skills: list[str]) -> str:
    lower = user_message.lower()
    if any(key in lower for key in ("feishu", "飞书", "lark")):
        return "feishu"
    if any(key in lower for key in ("code", "python", "bug", "test", "git", "代码", "重构")):
        return "code"
    if skills:
        return "general"
    return "general"


def _store_path(home: Path) -> Path:
    path = home / "state" / "task_patterns.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_store(home: Path) -> dict[str, Any]:
    path = _store_path(home)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_store(home: Path, data: dict[str, Any]) -> None:
    _store_path(home).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def record_task_observation(
    home: Path,
    *,
    assistant_id: str,
    user_message: str,
    increment: bool = True,
    agent_id: str | None = None,
    skills: list[str] | None = None,
) -> dict[str, Any]:
    signature = normalize_task_signature(user_message)
    store = _read_store(home)
    bucket = store.setdefault(assistant_id, {})
    entry = bucket.setdefault(
        signature,
        {"count": 0, "agents": [], "skills": [], "promoted_agent_id": ""},
    )
    if increment:
        entry["count"] = int(entry.get("count", 0)) + 1
    if agent_id and agent_id not in entry.get("agents", []):
        entry.setdefault("agents", []).append(agent_id)
    if skills:
        merged = set(entry.get("skills") or [])
        merged.update(skills)
        entry["skills"] = sorted(merged)
    _write_store(home, store)
    return entry


def format_promotion_prompt(note: str) -> str:
    return f"### 专家沉淀建议\n- {note}"


def maybe_promote_expert(
    home: Path,
    *,
    assistant_id: str,
    user_message: str,
    routing: RoutingContext,
    agent_registry: AgentRegistry,
    subagent_index: SubAgentIndex,
    settings: ExpertPromotionSettings,
) -> tuple[str | None, str | None]:
    """Return (promotion_prompt_line, created_agent_id)."""
    if not settings.enabled:
        return None, None

    signature = normalize_task_signature(user_message)
    store = _read_store(home)
    entry = store.get(assistant_id, {}).get(signature, {})
    count = int(entry.get("count", 0))
    promoted = str(entry.get("promoted_agent_id") or "")
    top_score = routing.fused_ranking[0].final_score if routing.fused_ranking else 0.0
    has_expert = bool(routing.fused_ranking) and top_score >= settings.score_threshold

    if promoted and agent_registry.get(promoted):
        return (
            format_promotion_prompt(
                f"相似任务曾绑定专家 `{promoted}`；若需执行可 dispatch，若仅解释请主控直接回答。"
            ),
            None,
        )

    if has_expert:
        return None, None

    if count < settings.min_repeat:
        if count == settings.min_repeat - 1:
            return format_promotion_prompt(
                f"相似任务第 {count + 1} 次出现，若无合适专家可考虑 create_subagent。"
            ), None
        return None, None

    skills = list(routing.suggested_skills[:5] or entry.get("skills") or [])
    domain = infer_domain(user_message, skills)
    agent_id = f"expert-{signature.replace(' ', '-')[:24]}" or "expert-general"
    config_mcp = {}
    try:
        import yaml

        cfg_path = home / "config.yaml"
        if cfg_path.exists():
            raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            mcp = raw.get("mcp_servers")
            if isinstance(mcp, dict):
                config_mcp = mcp
    except OSError:
        pass
    from agent.sedimentation import default_mcp_servers_for_domain

    mcp_servers = default_mcp_servers_for_domain(domain, config_mcp) if domain == "code" else []

    if not settings.auto_create:
        return format_promotion_prompt(
            f"重复任务（≥{settings.min_repeat} 次）建议创建专家 `{agent_id}`（domain={domain}）。"
        ), None

    if agent_registry.get(agent_id):
        return format_promotion_prompt(f"重复任务模式已匹配专家 `{agent_id}`。"), None

    toolsets = default_toolsets_for_domain(domain)
    description = f"Auto-promoted expert for repeated task pattern: {signature}"
    system_prompt = build_default_system_prompt(
        name=agent_id,
        domain=domain,
        description=description,
        skills=skills,
        toolsets=toolsets,
        mcp_servers=mcp_servers,
    )
    agent = AgentDefinition(
        agent_id=agent_id,
        assistant_id=assistant_id,
        name=agent_id.replace("-", " ").title(),
        domain=domain,
        description=description,
        system_prompt_template=system_prompt,
        skills=skills,
        toolsets=toolsets,
        mcp_servers=mcp_servers,
        stats={"auto_promoted": True, "task_signature": signature},
    )
    agent_registry.register(agent)
    subagent_index.sync_agent(agent)

    bucket = store.setdefault(assistant_id, {})
    pattern = bucket.setdefault(signature, {"count": count, "agents": [], "skills": skills})
    pattern["promoted_agent_id"] = agent_id
    _write_store(home, store)

    return (
        format_promotion_prompt(f"已自动创建专家 `{agent_id}`（重复任务 ≥{settings.min_repeat} 次）。"),
        agent_id,
    )
