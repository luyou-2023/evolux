from pathlib import Path

from agent.skill_router import SkillRouter


def test_skill_router_identify_by_keyword(evolux_home):
    skills_dir = evolux_home / "skills" / "git"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: git\ndescription: Git version control workflows\n---\n# Git\n",
        encoding="utf-8",
    )
    router = SkillRouter(evolux_home)
    hits = router.identify("help me with git commit", enable_vector=False)
    assert hits
    assert hits[0].skill_name == "git"


def test_skill_router_load_for_execution(evolux_home):
    skills_dir = evolux_home / "skills" / "git"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: git\ndescription: Git\n---\nUse git status first.\n",
        encoding="utf-8",
    )
    router = SkillRouter(evolux_home)
    content = router.load_for_execution(["git"])
    assert "git status" in content
