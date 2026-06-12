from agent.agent_registry import AgentDefinition
from vector.subagent_index import SubAgentIndex


def test_subagent_index_search_filters_assistant(evolux_home):
    from agent.agent_registry import AgentRegistry

    registry = AgentRegistry(home=evolux_home)
    registry.register(
        AgentDefinition(
            agent_id="code-expert",
            assistant_id="work",
            name="Code Expert",
            domain="code",
            description="Python development and debugging",
            skills=["git"],
        )
    )
    index = SubAgentIndex(evolux_home, registry=registry)
    index.sync_agent(registry.get("code-expert"))

    hits = index.search("python bug fix", assistant_id="work", top_k=3)
    assert hits
    assert hits[0][0] == "code-expert"

    empty = index.search("python", assistant_id="other", top_k=3)
    assert empty == []
