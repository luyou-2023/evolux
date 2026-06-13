from agent.sedimentation import (
    build_default_system_prompt,
    build_dispatch_context_slice,
    default_mcp_servers_for_domain,
)


def test_default_mcp_servers_for_code_domain():
    config = {
        "opencode": {"command": "npx"},
        "cdp-mcp": {"command": "node"},
        "feishu-api": {"command": "uvx"},
        "disabled": {"command": "x", "enabled": False},
    }
    assert default_mcp_servers_for_domain("code", config) == ["opencode", "cdp-mcp"]
    assert default_mcp_servers_for_domain("feishu", config) == []


def test_build_default_system_prompt_code_requires_mcp():
    prompt = build_default_system_prompt(
        name="OpenCode Expert",
        domain="code",
        description="Writes code via MCP",
        skills=["native-mcp"],
        toolsets=["evolux-code"],
        mcp_servers=["opencode"],
    )
    assert "mcp_opencode" in prompt or "MCP 工具" in prompt
    assert "write_file/terminal" in prompt


def test_build_dispatch_context_slice_injects_mcp_rules():
    ctx = build_dispatch_context_slice(
        toolsets=["evolux-code"],
        mcp_servers=["opencode"],
        domain="code",
        context_slice="User asked for hello world",
    )
    assert "User asked for hello world" in ctx
    assert "opencode" in ctx
    assert "write_file/terminal" in ctx
