"""Hermes-aligned skills_list and skill_view tools."""

from __future__ import annotations

import json
from pathlib import Path

from agent.skill_router import SkillRouter, parse_skill_md
from evolux_constants import get_evolux_home
from tools.registry import registry, tool_error


def skills_list(*, category: str | None = None) -> str:
    home = get_evolux_home()
    router = SkillRouter(home)
    skills = router.scan_skills()
    if category:
        prefix = f"{category}/"
        skills = [s for s in skills if str(s.path).replace("\\", "/").find(f"/{prefix}") >= 0 or s.skill_name.startswith(category)]
    payload = [
        {
            "name": skill.skill_name,
            "description": skill.description[:1024],
            "path": str(skill.path),
            "domain_tags": skill.domain_tags or [],
        }
        for skill in skills
    ]
    return json.dumps({"success": True, "skills": payload, "count": len(payload)}, ensure_ascii=False)


def skill_view(name: str, file_path: str | None = None) -> str:
    home = get_evolux_home()
    skills_dir = home / "skills"
    skill_dir = skills_dir / name
    target = skill_dir / (file_path or "SKILL.md")
    if not target.exists():
        return tool_error(f"skill file not found: {name}/{file_path or 'SKILL.md'}")

    resolved = target.resolve()
    if skills_dir.resolve() not in resolved.parents and resolved != skills_dir.resolve():
        return tool_error("path escapes skills directory")

    if target.name == "SKILL.md":
        meta = parse_skill_md(target)
        body = target.read_text(encoding="utf-8")
        return json.dumps(
            {
                "success": True,
                "name": meta.skill_name if meta else name,
                "description": meta.description if meta else "",
                "file": "SKILL.md",
                "content": body,
            },
            ensure_ascii=False,
        )

    content = target.read_text(encoding="utf-8")
    return json.dumps(
        {
            "success": True,
            "name": name,
            "file": file_path,
            "content": content,
        },
        ensure_ascii=False,
    )


def check_skills_requirements() -> bool:
    return True


SKILLS_LIST_SCHEMA = {
    "name": "skills_list",
    "description": "List installed skills with metadata only (Hermes progressive disclosure tier 1).",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "description": "Optional category prefix filter"},
        },
    },
}

SKILL_VIEW_SCHEMA = {
    "name": "skill_view",
    "description": "Load a skill's SKILL.md or linked reference file (Hermes tier 2).",
    "parameters": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Skill name"},
            "file_path": {
                "type": "string",
                "description": "Optional linked file path within the skill directory",
            },
        },
        "required": ["name"],
    },
}

registry.register(
    "skills_list",
    lambda args, **_: skills_list(category=args.get("category")),
    SKILLS_LIST_SCHEMA,
    toolset="skills",
    check_fn=check_skills_requirements,
)
registry.register(
    "skill_view",
    lambda args, **_: skill_view(name=args.get("name", ""), file_path=args.get("file_path")),
    SKILL_VIEW_SCHEMA,
    toolset="skills",
    check_fn=check_skills_requirements,
)
