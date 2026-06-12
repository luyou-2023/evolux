"""Skills management commands."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from agent.skill_router import SkillRouter
from evolux_constants import get_evolux_home

BUNDLED_SKILLS = Path(__file__).resolve().parents[1] / "skills" / "bundled"
LEGACY_OFFICIAL = Path(__file__).resolve().parents[1] / "skills" / "official"


def add_skills_parser(sub: argparse._SubParsersAction) -> None:
    skills = sub.add_parser("skills", help="Manage Skill definitions")
    skills_sub = skills.add_subparsers(dest="skills_command")

    skills_sub.add_parser("list", help="List installed skills")
    skills_sub.add_parser("reindex", help="Rebuild skill vector index")

    install = skills_sub.add_parser("install", help="Install a skill from path or bundled catalog")
    install.add_argument("source", help="Skill directory path or bundled skill name (e.g. git)")


def run_skills(args: argparse.Namespace, home: Path | None = None) -> int:
    base = home or get_evolux_home()
    router = SkillRouter(base)

    if args.skills_command == "list":
        skills = router.scan_skills()
        if not skills:
            print("No skills installed. Run: evolux skills install git")
            return 0
        for skill in skills:
            tags = ", ".join(skill.domain_tags or []) or "-"
            print(f"{skill.skill_name}\t{skill.description[:60]}\t[{tags}]")
        return 0

    if args.skills_command == "reindex":
        skills = router.scan_skills()
        print(f"Reindexed {len(skills)} skill(s) into vector store.")
        return 0

    if args.skills_command == "install":
        return _install_skill(base, args.source)

    return 1


def _install_skill(home: Path, source: str) -> int:
    src = Path(source).expanduser()
    if not src.is_absolute():
        for candidate in (BUNDLED_SKILLS / source, LEGACY_OFFICIAL / source, Path(source)):
            if candidate.exists():
                src = candidate.resolve()
                break
        else:
            print(f"Skill not found: {source}")
            print(f"Bundled skills: {_list_bundled_names()}")
            return 1
    elif not src.exists():
        print(f"Path not found: {src}")
        return 1

    skill_md = src / "SKILL.md"
    if not skill_md.exists():
        print(f"Missing SKILL.md in {src}")
        return 1

    skill_name = src.name
    from agent.skill_router import parse_skill_md

    meta = parse_skill_md(skill_md)
    if meta:
        skill_name = meta.skill_name

    dest = home / "skills" / skill_name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)

    router = SkillRouter(home)
    router.scan_skills()
    print(f"Installed skill '{skill_name}' -> {dest}")
    return 0


def _list_bundled_names() -> str:
    names: set[str] = set()
    for root in (BUNDLED_SKILLS, LEGACY_OFFICIAL):
        if root.exists():
            names.update(p.name for p in root.iterdir() if p.is_dir())
    return ", ".join(sorted(names)) or "(none)"
