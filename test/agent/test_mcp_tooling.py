from pathlib import Path

from agent.mcp_tooling import MCPToolRouter
from mcp.manager import MCPManager

FIXTURE_SERVER = Path(__file__).resolve().parents[1] / "fixtures" / "minimal_mcp_server.py"


def test_mcp_tool_router_discovers_and_dispatches(evolux_home):
    (evolux_home / "config.yaml").write_text(
        f"""
mcp_servers:
  echo:
    command: python3
    args: ["{FIXTURE_SERVER}"]
""".strip(),
        encoding="utf-8",
    )
    manager = MCPManager(home=evolux_home)
    router = MCPToolRouter(manager)
    tools = router.discover()
    assert any(t["name"] == "mcp_echo_echo" for t in tools)

    result = router.dispatch("mcp_echo_echo", {"text": "phase5"})
    assert "echo:phase5" in result
    manager.close()
