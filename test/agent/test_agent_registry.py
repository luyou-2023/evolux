from agent.agent_registry import AgentDefinition, AgentRegistry
import json


def test_agent_registry_register_and_get(evolux_home):
    registry = AgentRegistry(home=evolux_home)
    agent = AgentDefinition(
        agent_id="code-expert",
        assistant_id="default",
        name="Code Expert",
        domain="code",
        description="Python development",
        toolsets=["evolux-code"],
        skills=["git"],
    )
    registry.register(agent)
    loaded = registry.get("code-expert")
    assert loaded is not None
    assert loaded.name == "Code Expert"
    assert loaded.skills == ["git"]


def test_agent_registry_list_by_assistant(evolux_home):
    registry = AgentRegistry(home=evolux_home)
    registry.register(
        AgentDefinition(
            agent_id="a1",
            assistant_id="work",
            name="A1",
            domain="code",
            description="d1",
        )
    )
    registry.register(
        AgentDefinition(
            agent_id="a2",
            assistant_id="life",
            name="A2",
            domain="general",
            description="d2",
        )
    )
    work_agents = registry.list_by_assistant("work")
    assert [a.agent_id for a in work_agents] == ["a1"]


def test_agent_registry_retire_soft_deletes(evolux_home):
    registry = AgentRegistry(home=evolux_home)
    registry.register(
        AgentDefinition(
            agent_id="old",
            assistant_id="default",
            name="Old",
            domain="code",
            description="deprecated",
        )
    )
    registry.retire("old")
    assert registry.get("old") is None
    assert registry.get("old", include_retired=True) is not None


def test_agent_registry_legacy_agents_array(evolux_home):
    path = evolux_home / "agents" / "registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """{
  "agents": [],
  "_session-monitor": {
    "agent_id": "_session-monitor",
    "assistant_id": "default",
    "name": "Session Monitor",
    "domain": "orchestration",
    "description": "internal",
    "system_prompt_template": "",
    "toolsets": [],
    "skills": [],
    "mcp_servers": [],
    "retired": false,
    "stats": {}
  }
}""",
        encoding="utf-8",
    )
    registry = AgentRegistry(home=evolux_home)
    agents = registry.list_by_assistant("default")
    assert len(agents) == 1
    assert agents[0].agent_id == "_session-monitor"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "agents" not in raw
