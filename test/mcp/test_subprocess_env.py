from pathlib import Path
import os

from mcp.subprocess_env import (
    build_stdio_env,
    resolve_stdio_cwd,
    sanitize_subprocess_env,
)


def test_sanitize_subprocess_env_drops_evolux_repo_from_pythonpath(monkeypatch, tmp_path):
    repo = tmp_path / "evolux"
    (repo / "mcp").mkdir(parents=True)
    (repo / "agent").mkdir()
    (repo / "mcp" / "stdio_client.py").write_text("# stub", encoding="utf-8")
    (repo / "agent" / "runtime.py").write_text("# stub", encoding="utf-8")

    other = tmp_path / "other"
    other.mkdir()
    env = {
        "PATH": "/usr/bin",
        "PYTHONPATH": f"{repo}{os.pathsep}{other}",
    }
    sanitized = sanitize_subprocess_env(env, evolux_home=tmp_path / "home")
    assert str(repo) not in sanitized.get("PYTHONPATH", "")
    assert str(other) in sanitized["PYTHONPATH"]


def test_build_stdio_env_applies_server_overrides(evolux_home, monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    env = build_stdio_env({"FOO": "bar"}, evolux_home=evolux_home)
    assert env["FOO"] == "bar"
    assert env["PATH"] == "/usr/bin"


def test_resolve_stdio_cwd_from_script_path(tmp_path):
    script = tmp_path / "servers" / "run.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('ok')\n", encoding="utf-8")
    cwd = resolve_stdio_cwd({}, "python3", [str(script)])
    assert cwd == str(script.parent.resolve())


def test_mcp_manager_passes_env_and_cwd_to_stdio_client(evolux_home, monkeypatch):
    script = evolux_home / "servers" / "echo.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        """
import json, sys
msg = sys.stdin.readline()
while msg.strip():
    msg = sys.stdin.readline()
print('Content-Length: 0\\r\\r', end='')
""".strip(),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, command, args, *, env=None, cwd=None, home=None, sampling_handler=None, timeout=120.0, connect_timeout=60.0):
            captured["command"] = command
            captured["args"] = args
            captured["env"] = env
            captured["cwd"] = cwd
            captured["timeout"] = timeout
            captured["connect_timeout"] = connect_timeout

        def list_tools(self):
            return [{"name": "echo", "description": "echo", "inputSchema": {"type": "object"}}]

        def close(self):
            pass

    monkeypatch.setattr("mcp.manager.MCPStdioClient", FakeClient)
    (evolux_home / "config.yaml").write_text(
        f"""
mcp_servers:
  echo:
    command: python3
    args: ["{script}"]
    cwd: "{script.parent}"
    timeout: 15
    env:
      MCP_TEST: "1"
""".strip(),
        encoding="utf-8",
    )

    from mcp.manager import MCPManager

    manager = MCPManager(home=evolux_home)
    manager.discover_tools("echo")
    assert captured["cwd"] == str(script.parent.resolve())
    assert captured["env"]["MCP_TEST"] == "1"
    assert captured["timeout"] == 15.0
    assert captured["connect_timeout"] == 60.0
    manager.close()
