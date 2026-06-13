from agent.routing import (
    SubAgentCandidate,
    fuse_routing,
    looks_like_execution_task,
    routing_junk_penalty,
)


def test_looks_like_execution_task():
    assert looks_like_execution_task("用python写一个hello 运行 给出运行结果")
    assert looks_like_execution_task("python hello and run it")
    assert not looks_like_execution_task("python 是什么")


def test_routing_junk_penalty():
    assert routing_junk_penalty("expert-帮我把飞书集成进来-hermes-共用") < -0.5
    assert routing_junk_penalty("code-dev-expert") == 0.0


def test_execution_task_boosts_mcp_code_expert():
    candidates = [
        SubAgentCandidate("expert-帮我把飞书集成进来-hermes-共用", vector_score=0.9, skills=[]),
        SubAgentCandidate("code-dev-expert", vector_score=0.3, skills=["native-mcp"], domain="code"),
    ]
    ctx = fuse_routing(
        [],
        candidates,
        user_message="用python写一个hello 运行",
        agent_mcp={"code-dev-expert": True, "expert-帮我把飞书集成进来-hermes-共用": False},
        agent_domains={"code-dev-expert": "code"},
    )
    assert ctx.fused_ranking[0].agent_id == "code-dev-expert"
    assert "必须" in ctx.prompt_block
    assert "dispatch_subagent" in ctx.prompt_block
