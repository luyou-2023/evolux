from mcp.manager import MCPManager


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


def test_mcp_manager_discover_tools_stub(evolux_home):
    (evolux_home / "config.yaml").write_text(
        "mcp_servers:\n  db:\n    url: http://localhost:8080\n",
        encoding="utf-8",
    )
    manager = MCPManager(home=evolux_home)
    tools = manager.discover_tools("db")
    assert tools
    assert manager.discover_tools("db") is tools
