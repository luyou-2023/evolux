"""Post-turn extraction of durable facts into global MEMORY.md."""

from __future__ import annotations

import json
from typing import Any, Callable

from agent.memory_manager import MemoryManager

MemoryExtractFn = Callable[[str, str, list[dict[str, Any]]], list[str]]


def extract_memory_entries_heuristic(
    user_message: str,
    final_reply: str,
    dispatches: list[dict[str, Any]],
) -> list[str]:
    entries: list[str] = []
    user = user_message.strip()
    reply = (final_reply or "").strip()
    if not user or not reply:
        return entries

    if dispatches:
        agents = ", ".join(item["agent_id"] for item in dispatches)
        skills: set[str] = set()
        for item in dispatches:
            skills.update(item.get("skills") or [])
        skill_text = ", ".join(sorted(skills)) if skills else "-"
        entries.append(
            f"协调记录: 「{user[:160]}」→ 委派 [{agents}]，skills [{skill_text}]"
        )
    elif len(user) >= 12 and len(reply) >= 40:
        entries.append(f"对话要点: Q={user[:160]} / A={reply[:320]}")

    return entries


def sediment_global_memory(
    memory: MemoryManager,
    *,
    user_message: str,
    final_reply: str,
    dispatches: list[dict[str, Any]],
    extract_fn: MemoryExtractFn | None = None,
) -> list[str]:
    extractor = extract_fn or extract_memory_entries_heuristic
    entries = extractor(user_message, final_reply, dispatches)
    written: list[str] = []
    for entry in entries:
        text = entry.strip()
        if not text:
            continue
        memory.append_global_memory(text)
        written.append(text)
    return written


def extract_memory_entries_llm(
    llm_call,
    user_message: str,
    final_reply: str,
    dispatches: list[dict[str, Any]],
) -> list[str]:
    dispatch_text = ""
    if dispatches:
        dispatch_text = "Dispatches: " + ", ".join(
            f"{item['agent_id']}({','.join(item.get('skills') or [])})" for item in dispatches
        )
    prompt = (
        "Extract 0-2 durable facts worth saving to long-term memory.\n"
        "Return JSON array of short Chinese strings; return [] if nothing durable.\n\n"
        f"User: {user_message[:500]}\n"
        f"Assistant: {final_reply[:800]}\n"
        f"{dispatch_text}"
    )
    try:
        response = llm_call([{"role": "user", "content": prompt}])
        content = getattr(response, "content", None) or str(response)
        parsed = json.loads(content.strip())
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        return extract_memory_entries_heuristic(user_message, final_reply, dispatches)
    return extract_memory_entries_heuristic(user_message, final_reply, dispatches)
