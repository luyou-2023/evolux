import json
from unittest.mock import patch

from agent.agent_registry import AgentRegistry
from agent.expert_bootstrap import install_ui_automation_expert
from tools.midscene_luke_bridge import luke_engine_root
from tools.midscene_luke_tools import midscene_luke_init_tool, midscene_luke_status_tool
from vector.subagent_index import SubAgentIndex


def test_install_ui_automation_expert(evolux_home):
    registry = AgentRegistry(home=evolux_home)
    index = SubAgentIndex(evolux_home, registry=registry)
    agent = install_ui_automation_expert(registry, index, assistant_id="cdp-automation")
    assert agent.agent_id == "ui-automation-expert"
    assert agent.domain == "ui-test"
    assert "evolux-ui-test" in agent.toolsets
    assert "midscene-ui" in agent.skills
    loaded = registry.get("ui-automation-expert")
    assert loaded is not None
    assert "midscene_luke" in loaded.system_prompt_template


def test_midscene_luke_status_tool():
    out = json.loads(midscene_luke_status_tool({}))
    assert out["engine"] == "midscenejs_luke"
    assert "root" in out


def test_midscene_luke_init_project(evolux_home, monkeypatch):
    monkeypatch.setattr(
        "tools.midscene_luke_bridge.luke_engine_root",
        lambda: evolux_home / "midscenejs_luke",
    )
    engine = evolux_home / "midscenejs_luke"
    (engine / "templates" / "e2e").mkdir(parents=True)
    (engine / "templates" / "playwright.config.mjs").write_text("export default {}", encoding="utf-8")
    (engine / "templates" / "e2e" / "fixture.mjs").write_text("export {};", encoding="utf-8")
    (engine / "templates" / "e2e" / "smoke.spec.mjs").write_text("export {};", encoding="utf-8")

    out = json.loads(midscene_luke_init_tool({}))
    assert out["success"] is True
    assert (evolux_home / "ui-tests" / "e2e" / "fixture.mjs").exists()


def test_luke_engine_root_points_to_package():
    root = luke_engine_root()
    assert root.name == "midscenejs_luke"
    assert (root / "package.json").exists()
