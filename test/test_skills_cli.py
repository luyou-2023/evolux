import json

from cli.main import main
from cli.setup import run_setup


def test_skills_install_list_reindex(evolux_home):
    run_setup(home=evolux_home)
    assert main(["skills", "install", "git"]) == 0
    assert (evolux_home / "skills" / "git" / "SKILL.md").exists()
    assert main(["skills", "list"]) == 0
    assert main(["skills", "reindex"]) == 0
