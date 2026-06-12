import json

from model_tools import get_tool_definitions
from toolsets import resolve_toolset
from tools.discover import ensure_tools_loaded
from tools.registry import registry


def test_discover_loads_hermes_core_tools():
    ensure_tools_loaded()
    names = {entry.name for entry in [registry.get_entry(n) for n in [
        "skills_list", "skill_view", "memory", "session_search", "read_file", "write_file", "todo"
    ]] if entry}
    assert "skills_list" in names
    assert "memory" in names


def test_cli_platform_toolset_includes_orchestrator_tools():
    tools = get_tool_definitions(platform="cli")
    tool_names = {item["function"]["name"] for item in tools}
    assert "skills_list" in tool_names
    assert "dispatch_subagent" in tool_names


def test_hermes_acp_alias_resolves():
    names = resolve_toolset("hermes-acp")
    assert "read_file" in names
    assert "skill_view" in names
    assert "terminal" in names
    assert "web_search" in names


def test_cli_platform_includes_terminal_and_web():
    tools = get_tool_definitions(platform="cli")
    tool_names = {item["function"]["name"] for item in tools}
    assert "terminal" in tool_names
    assert "web_search" in tool_names
