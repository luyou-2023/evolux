from test.fixtures.minimal_mcp_http_server import start_server

from mcp.http_client import MCPHTTPClient


def test_mcp_http_client_lists_and_calls_tools():
    url, stop = start_server()
    try:
        client = MCPHTTPClient(url)
        tools = client.list_tools()
        assert tools[0]["name"] == "echo"
        result = client.call_tool("echo", {"text": "hello"})
        assert result["content"][0]["text"] == "echo:hello"
        client.close()
    finally:
        stop()
