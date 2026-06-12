from pathlib import Path

from cli.main import main
from cli.setup import run_setup
from gateway.assistant_registry import AssistantRegistry


def test_cli_version():
    assert main(["version"]) == 0
    # version string checked via stdout in integration; exit code suffices here


def test_cli_setup_creates_config(evolux_home, monkeypatch):
    monkeypatch.chdir(evolux_home)
    assert run_setup(home=evolux_home) == 0
    assert (evolux_home / "config.yaml").exists()


def test_cli_assistant_list(evolux_home):
    run_setup(home=evolux_home)
    assert main(["assistant", "list"]) == 0


def test_cli_assistant_bind_feishu(evolux_home):
    run_setup(home=evolux_home)
    code = main(
        [
            "assistant",
            "bind",
            "feishu",
            "--id",
            "work-bot",
            "--app-id",
            "cli_app",
            "--app-secret",
            "secret",
        ]
    )
    assert code == 0
    registry = AssistantRegistry(home=evolux_home)
    cfg = registry.get("work-bot")
    assert cfg.platforms["feishu"]["app_id"] == "cli_app"


def test_cli_gateway_start_requires_feishu(evolux_home):
    run_setup(home=evolux_home)
    assert main(["gateway", "start"]) == 1


def test_cli_gateway_start_with_feishu(evolux_home):
    run_setup(home=evolux_home)
    main(["assistant", "bind", "feishu", "--id", "work-bot", "--app-id", "app1"])
    assert main(["gateway", "start", "--check"]) == 0


def test_cli_dashboard_start_check(evolux_home):
    run_setup(home=evolux_home)
    assert main(["dashboard", "start", "--check"]) == 0
