from agent.routing import FusionWeights, SkillCandidate, SubAgentCandidate, fuse_routing
from run_agent import EvoluxAgent


def test_per_assistant_fusion_weights(evolux_home):
    (evolux_home / "config.yaml").write_text(
        """
assistants:
  work-bot:
    name: Work
    routing:
      fusion:
        vector_weight: 1.0
        skill_overlap_weight: 0.0
        recency_weight: 0.0
    platforms:
      cli: {}
""".strip(),
        encoding="utf-8",
    )

    agent = EvoluxAgent(
        llm_call=lambda _: type("R", (), {"content": "ok", "tool_calls": []})(),
        home=evolux_home,
        assistant_id="work-bot",
    )
    assert agent._fusion_weights() == FusionWeights(
        vector_weight=1.0,
        skill_overlap_weight=0.0,
        recency_weight=0.0,
    )

    skills = [SkillCandidate(skill_name="git", score=0.9)]
    subagents = [
        SubAgentCandidate(
            agent_id="a1",
            vector_score=0.2,
            skills=["git"],
            recency_boost=1.0,
        ),
        SubAgentCandidate(
            agent_id="a2",
            vector_score=0.9,
            skills=[],
            recency_boost=0.0,
        ),
    ]
    ctx = fuse_routing(skills, subagents, agent._fusion_weights())
    assert ctx.fused_ranking[0].agent_id == "a2"
    agent.close()
