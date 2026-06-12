import json

from tools.discover import ensure_tools_loaded
from tools.registry import registry


def test_terminal_echo(evolux_home):
    ensure_tools_loaded()
    raw = registry.dispatch("terminal", {"command": "echo hello", "cwd": str(evolux_home)})
    payload = json.loads(raw)
    assert payload["success"] is True
    assert "hello" in payload["stdout"]


def test_terminal_blocks_dangerous_command():
    ensure_tools_loaded()
    raw = registry.dispatch("terminal", {"command": "rm -rf /"})
    payload = json.loads(raw)
    assert payload["success"] is False
