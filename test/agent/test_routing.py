from agent.routing import (
    FusionWeights,
    SkillCandidate,
    SubAgentCandidate,
    fuse_routing,
    routing_decision_hints,
    skill_overlap,
)


def test_skill_overlap_ratio():
    skills = [SkillCandidate("git", 0.9), SkillCandidate("docker", 0.8)]
    assert skill_overlap(["git", "python"], skills) == 0.5


def test_fuse_routing_boosts_agent_with_matching_skills():
    skills = [SkillCandidate("git", 0.9)]
    agents = [
        SubAgentCandidate("code-expert", vector_score=0.6, skills=["git", "docker"]),
        SubAgentCandidate("feishu-expert", vector_score=0.8, skills=["feishu-doc"]),
    ]
    result = fuse_routing(skills, agents, FusionWeights())
    assert result.fused_ranking[0].agent_id == "code-expert"


def test_fuse_routing_prompt_contains_skill_and_agent():
    skills = [SkillCandidate("git", 0.9, description="Git workflows")]
    agents = [SubAgentCandidate("code-expert", vector_score=0.7, skills=["git"])]
    result = fuse_routing(skills, agents)
    assert "git" in result.prompt_block
    assert "code-expert" in result.prompt_block
    assert "供主控参考" in result.prompt_block


def test_routing_decision_hints_reuse_strong_match():
    skills = [SkillCandidate("git", 0.9)]
    agents = [SubAgentCandidate("code-expert", vector_score=0.9, skills=["git"])]
    ctx = fuse_routing(skills, agents)
    hints = routing_decision_hints(ctx)
    assert any(h.startswith("reuse_candidate: code-expert") for h in hints)
    assert any(h.startswith("orchestrator_skills:") for h in hints)


def test_routing_decision_hints_no_expert():
    ctx = fuse_routing([], [])
    hints = routing_decision_hints(ctx)
    assert hints == ["no_registered_expert: create_subagent only if execution-heavy and repeatable"]
