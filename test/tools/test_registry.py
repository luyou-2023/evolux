import json

from tools.registry import clear_registry, dispatch, register, registry


def setup_function():
    clear_registry()


def test_registry_dispatch_registered_tool():
    registry.clear()
    register("add", lambda args: {"sum": args["a"] + args["b"]}, {"name": "add", "parameters": {}})
    out = dispatch("add", {"a": 1, "b": 2})
    assert json.loads(out)["sum"] == 3


def test_registry_dispatch_unknown_tool():
    out = dispatch("missing", {})
    assert "error" in json.loads(out)
