import json

from agent.agent_registry import AgentDefinition, AgentRegistry
from agent.memory_manager import MemoryManager
from agent.planning_state import TurnPlanningState
from agent.routing import SkillCandidate, fuse_routing
from agent.sedimentation import build_default_system_prompt, sediment_agent_task
from agent.skill_router import SkillRouter
from run_agent import EvoluxAgent
from tools.orchestrator_tools import OrchestratorToolContext, handle_orchestrator_tool
from vector.subagent_index import SubAgentIndex


def test_orchestrator_turn_injects_planning_prompt(evolux_home):
    agent = EvoluxAgent(
        home=evolux_home,
        llm_call=lambda _: type("R", (), {"content": "ok", "tool_calls": []})(),
    )
    routing = agent.prepare_routing("build api")
    prefix = agent._build_prefix_messages(routing)
    system_contents = [m["content"] for m in prefix if m["role"] == "system"]
    assert any("主控 Agent" in content for content in system_contents)
    assert any("路由预检" in content for content in system_contents)
    agent.close()


def test_create_subagent_applies_routing_defaults(evolux_home):
    (evolux_home / "config.yaml").write_text(
        "mcp_servers:\n  opencode:\n    command: npx\n  cdp-mcp:\n    command: node\n",
        encoding="utf-8",
    )
    registry = AgentRegistry(home=evolux_home)
    planning = TurnPlanningState()
    planning.routing = fuse_routing(
        [SkillCandidate(skill_name="git", score=0.9, description="Git")],
        [],
    )
    ctx = OrchestratorToolContext(
        assistant_id="default",
        agent_registry=registry,
        subagent_index=SubAgentIndex(evolux_home, registry=registry),
        skill_router=SkillRouter(evolux_home),
        prepare_routing=lambda q: fuse_routing([], []),
        create_subagent_runner=lambda **_: {},
        dispatch_subagent=lambda **_: {"content": "ok"},
        turn_planning=planning,
        home=evolux_home,
    )
    out = json.loads(
        handle_orchestrator_tool(
            "create_subagent",
            {
                "agent_id": "code-expert",
                "name": "Code Expert",
                "domain": "code",
                "description": "Python specialist",
            },
            ctx,
        )
    )
    assert out["created"] == "code-expert"
    assert out["skills"] == ["git"]
    assert out["toolsets"] == ["evolux-code"]
    assert out["mcp_servers"] == ["opencode", "cdp-mcp"]
    agent = registry.get("code-expert")
    assert agent.system_prompt_template
    assert "Code Expert" in agent.system_prompt_template


def test_create_subagent_with_explicit_profile(evolux_home):
    registry = AgentRegistry(home=evolux_home)
    ctx = OrchestratorToolContext(
        assistant_id="default",
        agent_registry=registry,
        subagent_index=SubAgentIndex(evolux_home, registry=registry),
        skill_router=SkillRouter(evolux_home),
        prepare_routing=lambda q: fuse_routing([], []),
        create_subagent_runner=lambda **_: {},
        dispatch_subagent=lambda **_: {"content": "ok"},
    )
    out = json.loads(
        handle_orchestrator_tool(
            "create_subagent",
            {
                "agent_id": "feishu-bot",
                "name": "Feishu Bot",
                "domain": "feishu",
                "description": "Docs",
                "skills": ["feishu"],
                "toolsets": ["evolux-feishu"],
                "mcp_servers": ["my-mcp"],
                "system_prompt_template": "Custom prompt.",
            },
            ctx,
        )
    )
    agent = registry.get("feishu-bot")
    assert agent.system_prompt_template == "Custom prompt."
    assert agent.mcp_servers == ["my-mcp"]
    assert out["toolsets"] == ["evolux-feishu"]


def test_dispatch_sediments_agent_memory(evolux_home):
    skills_dir = evolux_home / "skills" / "git"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: git\ndescription: Git\n---\nUse git status.\n",
        encoding="utf-8",
    )
    agent = EvoluxAgent(
        home=evolux_home,
        llm_call=lambda _: type("R", (), {"content": "fixed bug in foo.py", "tool_calls": []})(),
    )
    agent.agent_registry.register(
        AgentDefinition(
            agent_id="code-expert",
            assistant_id="default",
            name="Code Expert",
            domain="code",
            description="Python",
            skills=["git"],
            system_prompt_template="You are a coder.",
        )
    )
    agent._turn_planning.reset(user_message="fix bug")
    agent.dispatch_subagent(agent_id="code-expert", task="fix bug", skills=["git"])
    memory = MemoryManager(home=evolux_home).read_agent_memory("code-expert")
    assert "fixed bug in foo.py" in memory
    assert "fix bug" in memory
    agent.close()


def test_dispatch_loads_prior_agent_memory(evolux_home):
    mem = MemoryManager(home=evolux_home)
    mem.append_agent_memory("code-expert", "Always run tests after edits.")

    captured = {"messages": None}

    def llm_call(messages):
        captured["messages"] = messages
        return type("R", (), {"content": "done", "tool_calls": []})()

    agent = EvoluxAgent(home=evolux_home, llm_call=llm_call)
    agent.agent_registry.register(
        AgentDefinition(
            agent_id="code-expert",
            assistant_id="default",
            name="Code Expert",
            domain="code",
            description="Python",
            skills=[],
            system_prompt_template="You are a coder.",
        )
    )
    agent._turn_planning.reset()
    agent.dispatch_subagent(agent_id="code-expert", task="run tests")
    system = next(m["content"] for m in captured["messages"] if m["role"] == "system")
    assert "Always run tests after edits." in system
    agent.close()


def test_max_concurrent_subagents_blocks(evolux_home):
    agent = EvoluxAgent(
        home=evolux_home,
        llm_call=lambda _: type("R", (), {"content": "ok", "tool_calls": []})(),
        settings=__import__("agent.settings", fromlist=["Settings"]).Settings(
            orchestrator_max_concurrent_subagents=1,
        ),
    )
    agent.agent_registry.register(
        AgentDefinition(
            agent_id="worker",
            assistant_id="default",
            name="Worker",
            domain="general",
            description="worker",
        )
    )
    agent._turn_planning.reset()
    first = agent.dispatch_subagent(agent_id="worker", task="task one")
    assert "error" not in first
    second = agent.orchestrator.tool_executor(
        {
            "name": "dispatch_subagent",
            "arguments": {"agent_id": "worker", "task": "task two"},
        }
    )
    payload = json.loads(second)
    assert "max concurrent subagents" in payload["error"]
    agent.close()


def test_turn_sediments_solution_after_dispatch(evolux_home):
    skills_dir = evolux_home / "skills" / "git"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text(
        "---\nname: git\ndescription: Git\n---\n",
        encoding="utf-8",
    )

    calls = {"n": 0}

    def llm_call(messages):
        calls["n"] += 1
        if calls["n"] == 1:
            return type(
                "R",
                (),
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "1",
                            "type": "function",
                            "function": {
                                "name": "dispatch_subagent",
                                "arguments": json.dumps(
                                    {
                                        "agent_id": "code-expert",
                                        "task": "review code",
                                        "skills": ["git"],
                                    }
                                ),
                            },
                        }
                    ],
                },
            )()
        return type("R", (), {"content": "Review complete.", "tool_calls": []})()

    sub_calls = {"n": 0}

    def sub_llm(_messages):
        sub_calls["n"] += 1
        return type("R", (), {"content": "LGTM", "tool_calls": []})()

    agent = EvoluxAgent(home=evolux_home, llm_call=llm_call)
    agent.orchestrator.llm_call = llm_call
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

    original_dispatch = agent.dispatch_subagent

    def dispatch_with_sub_llm(**kwargs):
        saved = agent.orchestrator.llm_call
        agent.orchestrator.llm_call = sub_llm
        try:
            return original_dispatch(**kwargs)
        finally:
            agent.orchestrator.llm_call = saved

    agent.dispatch_subagent = dispatch_with_sub_llm
    agent._tool_context.dispatch_subagent = dispatch_with_sub_llm

    agent.run_orchestrator_turn("orchestrator:default:cli:dm:sed", "please review my code")
    solutions = MemoryManager(home=evolux_home).read_solutions_snapshot()
    assert "code-expert" in solutions
    assert "Review complete." in solutions
    agent.close()


def test_build_default_system_prompt_includes_bindings():
    prompt = build_default_system_prompt(
        name="Coder",
        domain="code",
        description="Writes Python",
        skills=["git"],
        toolsets=["evolux-code"],
        mcp_servers=["fs"],
    )
    assert "Coder" in prompt
    assert "git" in prompt
    assert "evolux-code" in prompt
    assert "fs" in prompt
