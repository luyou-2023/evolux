import json

from cli.setup import run_setup
from tools.discover import ensure_tools_loaded
from tools.skills_tool import skills_list, skill_view


def test_skills_list_and_view(evolux_home):
    run_setup(home=evolux_home)
    ensure_tools_loaded()
    listed = json.loads(skills_list())
    assert listed["success"] is True
    assert listed["count"] >= 1

    first = listed["skills"][0]["name"]
    viewed = json.loads(skill_view(first))
    assert viewed["success"] is True
    assert "content" in viewed
