import json

from agent.agent_registry import AgentDefinition
from run_agent import EvoluxAgent


def test_prepare_routing_returns_fused_candidates(evolux_home):
    registry_path = evolux_home / "agents" / "registry.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)

    skills_dir = evolux_home / "skills" / "git"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: git\ndescription: Git version control\n---\n",
        encoding="utf-8",
    )

    agent = EvoluxAgent(
        home=evolux_home,
        llm_call=lambda _: type("R", (), {"content": "ok", "tool_calls": []})(),
    )
    agent.agent_registry.register(
        AgentDefinition(
            agent_id="code-expert",
            assistant_id="default",
            name="Code Expert",
            domain="code",
            description="Python development",
            skills=["git"],
        )
    )
    agent.subagent_index.sync_agent(agent.agent_registry.get("code-expert"))

    routing = agent.prepare_routing("help with git commit")
    assert routing.skill_candidates
    assert routing.fused_ranking
    assert routing.fused_ranking[0].agent_id == "code-expert"
    assert "路由预检" in routing.prompt_block
    agent.close()


def test_run_orchestrator_turn_injects_routing_block(evolux_home):
    captured = {"messages": None}

    def llm_call(messages):
        captured["messages"] = messages
        return type("R", (), {"content": "reply", "tool_calls": []})()

    agent = EvoluxAgent(home=evolux_home, llm_call=llm_call)
    agent.run_orchestrator_turn("orchestrator:default:cli:dm:u1", "hello")
    assert captured["messages"] is not None
    system_contents = [m["content"] for m in captured["messages"] if m["role"] == "system"]
    assert any("路由预检" in content for content in system_contents)
    assert any("主控 Agent" in content for content in system_contents)
    agent.close()


def test_dispatch_subagent_tool_via_executor(evolux_home):
    skills_dir = evolux_home / "skills" / "git"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: git\ndescription: Git\n---\nUse git status.\n",
        encoding="utf-8",
    )

    agent = EvoluxAgent(
        home=evolux_home,
        llm_call=lambda _: type("R", (), {"content": "done", "tool_calls": []})(),
    )
    agent.agent_registry.register(
        AgentDefinition(
            agent_id="code-expert",
            assistant_id="default",
            name="Code Expert",
            domain="code",
            description="Python",
            skills=["git"],
        )
    )

    out = agent.orchestrator.tool_executor(
        {
            "name": "dispatch_subagent",
            "arguments": {
                "agent_id": "code-expert",
                "task": "fix tests",
                "skills": ["git"],
            },
        }
    )
    payload = json.loads(out)
    assert payload["agent_id"] == "code-expert"
    assert payload["content"] == "done"
    agent.close()
