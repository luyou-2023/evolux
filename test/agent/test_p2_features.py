import json

from agent.expert_promotion import (
    maybe_promote_expert,
    normalize_task_signature,
    record_task_observation,
)
from agent.agent_registry import AgentRegistry
from agent.goals_manager import GoalsManager
from agent.mcp_proposals import persist_mcp_server_to_config
from agent.planning_state import TurnPlanningState
from agent.routing import fuse_routing
from agent.session_plan import load_session_plan
from agent.settings import ExpertPromotionSettings
from agent.skill_router import SkillRouter
from agent.slash_commands import SlashCommandContext, try_handle_slash_command
from evolux_state import SessionDB
from run_agent import EvoluxAgent
from tools.orchestrator_tools import OrchestratorToolContext, handle_orchestrator_tool
from vector.subagent_index import SubAgentIndex


def test_goals_manager_add_and_snapshot(evolux_home):
    manager = GoalsManager(home=evolux_home)
    goal = manager.add_goal("Ship auth refactor")
    assert goal.goal_id.startswith("goal-")
    snapshot = manager.read_snapshot()
    assert "Ship auth refactor" in snapshot
    assert manager.mark_done(goal.goal_id)
    assert manager.read_snapshot() == ""


def test_slash_goal_add(evolux_home):
    db = SessionDB(home=evolux_home)
    key = "orchestrator:default:cli:dm:goal"
    outcome = try_handle_slash_command(
        "/goal add Launch beta",
        ctx=SlashCommandContext(
            session_key=key,
            assistant_id="default",
            platform="cli",
            session_db=db,
            home=evolux_home,
            goals_manager=GoalsManager(home=evolux_home),
        ),
    )
    assert outcome and "Launch beta" in (outcome.reply or "")
    snapshot = GoalsManager(home=evolux_home).read_snapshot()
    assert "Launch beta" in snapshot


def test_plan_task_persists_session_plan(evolux_home):
    planning = TurnPlanningState()
    planning.session_key = "orchestrator:default:cli:dm:plan"
    ctx = OrchestratorToolContext(
        assistant_id="default",
        agent_registry=AgentRegistry(home=evolux_home),
        subagent_index=SubAgentIndex(evolux_home),
        skill_router=SkillRouter(evolux_home),
        prepare_routing=lambda q: fuse_routing([], []),
        create_subagent_runner=lambda **_: {},
        dispatch_subagent=lambda **_: {"content": "ok"},
        turn_planning=planning,
        home=evolux_home,
    )
    out = json.loads(
        handle_orchestrator_tool(
            "plan_task",
            {
                "goal": "Review codebase",
                "steps": [{"action": "Scan repo", "agent_id": "code-expert"}],
            },
            ctx,
        )
    )
    assert out["planned"] is True
    block = load_session_plan(evolux_home, planning.session_key)
    assert "Review codebase" in block
    assert "code-expert" in block


def test_expert_auto_promotion_on_repeat(evolux_home):
    registry = AgentRegistry(home=evolux_home)
    index = SubAgentIndex(evolux_home, registry=registry)
    settings = ExpertPromotionSettings(min_repeat=2, auto_create=True, score_threshold=0.9)
    message = "help me refactor python asyncio code"
    record_task_observation(evolux_home, assistant_id="default", user_message=message)
    routing = fuse_routing([], [])
    prompt, created = maybe_promote_expert(
        evolux_home,
        assistant_id="default",
        user_message=message,
        routing=routing,
        agent_registry=registry,
        subagent_index=index,
        settings=settings,
    )
    assert created is None
    record_task_observation(evolux_home, assistant_id="default", user_message=message)
    prompt, created = maybe_promote_expert(
        evolux_home,
        assistant_id="default",
        user_message=message,
        routing=routing,
        agent_registry=registry,
        subagent_index=index,
        settings=settings,
    )
    assert created is not None
    assert registry.get(created) is not None
    assert prompt and "自动创建" in prompt


def test_expert_promotion_suggests_without_auto_create(evolux_home):
    registry = AgentRegistry(home=evolux_home)
    index = SubAgentIndex(evolux_home, registry=registry)
    settings = ExpertPromotionSettings(min_repeat=2, auto_create=False, score_threshold=0.9)
    message = "help me refactor python asyncio code"
    record_task_observation(evolux_home, assistant_id="default", user_message=message)
    routing = fuse_routing([], [])
    record_task_observation(evolux_home, assistant_id="default", user_message=message)
    prompt, created = maybe_promote_expert(
        evolux_home,
        assistant_id="default",
        user_message=message,
        routing=routing,
        agent_registry=registry,
        subagent_index=index,
        settings=settings,
    )
    assert created is None
    assert prompt and "建议创建专家" in prompt
    assert registry.list_by_assistant("default") == []


def test_propose_and_approve_mcp(evolux_home):
    approved: dict[str, dict] = {}

    def on_approve(name, config):
        approved[name] = config

    ctx = OrchestratorToolContext(
        assistant_id="default",
        agent_registry=AgentRegistry(home=evolux_home),
        subagent_index=SubAgentIndex(evolux_home),
        skill_router=SkillRouter(evolux_home),
        prepare_routing=lambda q: fuse_routing([], []),
        create_subagent_runner=lambda **_: {},
        dispatch_subagent=lambda **_: {"content": "ok"},
        home=evolux_home,
    )
    out = json.loads(
        handle_orchestrator_tool(
            "propose_mcp_server",
            {
                "name": "demo",
                "transport": "stdio",
                "command": "echo",
                "args": ["mcp"],
                "reason": "demo server",
            },
            ctx,
        )
    )
    assert out["proposed"] == "demo"
    outcome = try_handle_slash_command(
        "/mcp approve demo",
        ctx=SlashCommandContext(
            session_key="orchestrator:default:cli:dm:mcp",
            assistant_id="default",
            platform="cli",
            session_db=SessionDB(home=evolux_home),
            home=evolux_home,
            on_mcp_approved=on_approve,
        ),
    )
    assert outcome and "批准" in (outcome.reply or "")
    assert "demo" in approved
    persist_mcp_server_to_config(evolux_home, "demo", approved["demo"])
    raw = (evolux_home / "config.yaml").read_text(encoding="utf-8")
    assert "demo:" in raw


def test_orchestrator_prefix_includes_goals(evolux_home):
    GoalsManager(home=evolux_home).add_goal("Improve routing quality")
    agent = EvoluxAgent(
        home=evolux_home,
        llm_call=lambda _: type("R", (), {"content": "ok", "tool_calls": []})(),
    )
    routing = agent.prepare_routing("hello")
    prefix = agent._build_prefix_messages(
        routing,
        session_key="orchestrator:default:cli:dm:goals",
    )
    contents = [m["content"] for m in prefix if m["role"] == "system"]
    assert any("Improve routing quality" in content for content in contents)
    agent.close()


def test_normalize_task_signature():
    sig = normalize_task_signature("Please help me fix Python asyncio bug")
    assert "python" in sig
    assert "asyncio" in sig
    assert "please" not in sig.split()
