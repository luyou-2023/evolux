from pathlib import Path

from mcp.manager import MCPManager
from mcp.stdio_client import MCPStdioClient


FIXTURE_SERVER = Path(__file__).resolve().parents[1] / "fixtures" / "minimal_mcp_server.py"


def test_mcp_manager_lists_servers(evolux_home):
    (evolux_home / "config.yaml").write_text(
        """
mcp_servers:
  filesystem:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
""".strip(),
        encoding="utf-8",
    )
    manager = MCPManager(home=evolux_home)
    servers = manager.list_servers()
    assert len(servers) == 1
    assert servers[0].name == "filesystem"


def test_mcp_stdio_client_lists_tools():
    client = MCPStdioClient("python3", [str(FIXTURE_SERVER)])
    tools = client.list_tools()
    client.close()
    assert len(tools) == 1
    assert tools[0]["name"] == "echo"


def test_mcp_stdio_client_calls_tool():
    client = MCPStdioClient("python3", [str(FIXTURE_SERVER)])
    result = client.call_tool("echo", {"text": "hello"})
    client.close()
    assert result["content"][0]["text"] == "echo:hello"


def test_mcp_manager_discovers_stdio_tools(evolux_home):
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
    tools = manager.discover_tools("echo")
    assert len(tools) == 1
    assert tools[0]["name"] == "mcp_echo_echo"
    assert tools[0]["mcp_tool"] == "echo"
    assert manager.discover_tools("echo") is tools

    result = manager.call_tool("echo", "echo", {"text": "evolux"})
    assert result["content"][0]["text"] == "echo:evolux"
    manager.close()


def test_mcp_manager_discovers_http_tools(evolux_home):
    from test.fixtures.minimal_mcp_http_server import start_server

    url, stop = start_server()
    try:
        (evolux_home / "config.yaml").write_text(
            f"mcp_servers:\n  echo:\n    url: {url}\n",
            encoding="utf-8",
        )
        manager = MCPManager(home=evolux_home)
        tools = manager.discover_tools("echo")
        assert len(tools) == 1
        assert tools[0]["name"] == "mcp_echo_echo"
        result = manager.call_tool("echo", "echo", {"text": "http"})
        assert result["content"][0]["text"] == "echo:http"
        manager.close()
    finally:
        stop()
