from pathlib import Path

from mcp.manager import MCPManager
from mcp.registry_bridge import sync_mcp_tools
from tools.discover import ensure_tools_loaded
from tools.registry import registry

FIXTURE_SERVER = Path(__file__).resolve().parents[1] / "fixtures" / "minimal_mcp_server.py"


def test_mcp_registry_bridge_registers_tools(evolux_home):
    (evolux_home / "config.yaml").write_text(
        f"""
mcp_servers:
  echo:
    command: python3
    args: ["{FIXTURE_SERVER}"]
""".strip(),
        encoding="utf-8",
    )
    ensure_tools_loaded()
    manager = MCPManager(home=evolux_home)
    names = sync_mcp_tools(manager, "echo")
    assert names == ["mcp_echo_echo"]
    out = registry.dispatch("mcp_echo_echo", {"text": "hermes"})
    assert "echo:hermes" in out
    manager.close()
