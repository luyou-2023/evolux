from agent.llm import MockLLMClient, llm_call_adapter
from model_tools import apply_mcp_allowlist, get_subagent_tool_definitions, get_tool_definitions
from tools.discover import ensure_tools_loaded
from tools.registry import registry


def test_llm_call_adapter_passes_tools_to_client():
    client = MockLLMClient(default_content="ok")
    call = llm_call_adapter(client)
    tools = [{"type": "function", "function": {"name": "terminal", "parameters": {}}}]
    call([{"role": "user", "content": "hi"}], tools=tools)
    assert client.last_tools == tools


def test_conversation_loop_passes_tools_to_llm_call():
    seen = {"tools": None}

    def llm_call(messages, **kwargs):
        seen["tools"] = kwargs.get("tools")
        return type("R", (), {"content": "done", "tool_calls": []})()

    from agent.conversation_loop import run_conversation_loop

    tools = [{"type": "function", "function": {"name": "todo", "parameters": {}}}]
    run_conversation_loop(
        [{"role": "user", "content": "plan"}],
        llm_call=llm_call,
        max_iterations=1,
        tools=tools,
    )
    assert seen["tools"] == tools


def test_apply_mcp_allowlist_filters_by_server():
    names = {"terminal", "mcp_echo_echo", "mcp_db_query"}
    filtered = apply_mcp_allowlist(names, ["echo"])
    assert "terminal" in filtered
    assert "mcp_echo_echo" in filtered
    assert "mcp_db_query" not in filtered


def test_subagent_tool_definitions_exclude_orchestrator_tools():
    ensure_tools_loaded()
    defs = get_subagent_tool_definitions(toolsets=["evolux-code"], mcp_servers=[])
    names = {item["function"]["name"] for item in defs if item.get("function")}
    assert "terminal" in names
    assert "dispatch_subagent" not in names


def test_orchestrator_platform_includes_dispatch_subagent():
    ensure_tools_loaded()
    defs = get_tool_definitions(platform="cli", include_mcp=False)
    names = {item["function"]["name"] for item in defs if item.get("function")}
    assert "dispatch_subagent" in names


def test_registry_list_names_by_toolset_prefix():
    ensure_tools_loaded()
    registry.register(
        "mcp_test_demo",
        lambda args, **_: "ok",
        {"name": "mcp_test_demo", "parameters": {"type": "object", "properties": {}}},
        toolset="mcp-test",
        override=True,
    )
    assert "mcp_test_demo" in registry.list_names(toolset_prefix="mcp-")
