from pathlib import Path

from mcp.manager import MCPManager
from mcp.sampling import MCPSamplingHandler, normalize_sampling_messages

SAMPLING_SERVER = Path(__file__).resolve().parents[1] / "fixtures" / "sampling_mcp_server.py"


def test_normalize_sampling_messages_flattens_text_blocks():
    messages = normalize_sampling_messages(
        [{"role": "user", "content": {"type": "text", "text": "hello"}}]
    )
    assert messages == [{"role": "user", "content": "hello"}]


def test_mcp_sampling_handler_returns_assistant_message():
    def llm_call(messages, **kwargs):
        return type("R", (), {"content": "sampled reply", "tool_calls": []})()

    handler = MCPSamplingHandler(llm_call, model="test-model")
    result = handler.create_message(
        {"messages": [{"role": "user", "content": {"type": "text", "text": "hi"}}]}
    )
    assert result["content"]["text"] == "sampled reply"
    assert result["model"] == "test-model"
    assert handler.stats.requests == 1


def test_mcp_manager_sampling_tool_call_uses_host_llm(evolux_home):
    def llm_call(messages, **kwargs):
        return type("R", (), {"content": "from-host-llm", "tool_calls": []})()

    (evolux_home / "config.yaml").write_text(
        f"""
mcp:
  sampling:
    enabled: true
mcp_servers:
  sampler:
    command: python3
    args: ["{SAMPLING_SERVER}"]
""".strip(),
        encoding="utf-8",
    )
    manager = MCPManager(home=evolux_home, llm_call=llm_call)
    tools = manager.discover_tools("sampler")
    assert tools[0]["name"] == "mcp_sampler_ask"

    result = manager.call_tool("sampler", "ask", {"prompt": "summarize"})
    assert result["content"][0]["text"] == "sampled:from-host-llm"
    assert manager.get_mcp_status()["sampler"]["requests"] == 1
    manager.close()
