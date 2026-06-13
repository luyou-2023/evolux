from cli.feishu_setup import resolve_feishu_bind_mode, run_feishu_app_wizard
from cli.main import main
from cli.setup import run_setup
from gateway.assistant_registry import AssistantRegistry


def test_resolve_feishu_bind_mode_auto_websocket(evolux_home, monkeypatch):
    monkeypatch.setattr(
        "gateway.platforms.feishu_hermes.hermes_gateway_running",
        lambda home=None: False,
    )
    assert resolve_feishu_bind_mode(requested="auto", home=evolux_home) == "websocket"


def test_resolve_feishu_bind_mode_auto_shared_hermes(evolux_home, monkeypatch):
    monkeypatch.setattr(
        "gateway.platforms.feishu_hermes.hermes_gateway_running",
        lambda home=None: True,
    )
    assert resolve_feishu_bind_mode(requested="auto", home=evolux_home) == "shared_hermes"


def test_feishu_wizard_binds_assistant(evolux_home, monkeypatch):
    run_setup(home=evolux_home)
    monkeypatch.setattr("cli.feishu_setup.feishu_register_app_available", lambda: True)

    def fake_register(**kwargs):
        kwargs["on_qr_code"]({"url": "https://open.feishu.cn/page/launcher?user_code=TEST", "expire_in": 600})
        return {
            "client_id": "cli_test_app",
            "client_secret": "cli_test_secret",
            "user_info": {"open_id": "ou_test"},
        }

    registry = AssistantRegistry(home=evolux_home)
    result = run_feishu_app_wizard(
        registry,
        assistant_id="work-bot",
        mode="websocket",
        open_browser=False,
        register_fn=fake_register,
    )
    assert result.app_id == "cli_test_app"
    cfg = registry.get("work-bot")
    assert cfg.platforms["feishu"]["app_secret"] == "cli_test_secret"
    assert cfg.platforms["feishu"]["mode"] == "websocket"


def test_cli_feishu_setup_command(evolux_home, monkeypatch):
    run_setup(home=evolux_home)
    monkeypatch.setattr("cli.feishu_cmd.feishu_register_app_available", lambda: True)

    def fake_wizard(registry, **kwargs):
        registry.bind_platform(
            kwargs["assistant_id"],
            "feishu",
            {"app_id": "cli_a", "app_secret": "sec", "mode": "websocket"},
        )
        from cli.feishu_setup import FeishuSetupResult

        return FeishuSetupResult(
            assistant_id=kwargs["assistant_id"],
            app_id="cli_a",
            app_secret="sec",
            mode="websocket",
        )

    monkeypatch.setattr("cli.feishu_cmd.run_feishu_app_wizard", fake_wizard)
    assert main(["feishu", "setup", "--assistant", "default"]) == 0
    cfg = AssistantRegistry(home=evolux_home).get("default")
    assert cfg.platforms["feishu"]["app_id"] == "cli_a"


def test_cli_assistant_bind_feishu_wizard(evolux_home, monkeypatch):
    run_setup(home=evolux_home)
    monkeypatch.setattr("cli.assistant.feishu_register_app_available", lambda: True)
    monkeypatch.setattr(
        "cli.assistant.run_feishu_app_wizard",
        lambda registry, **kwargs: type(
            "R",
            (),
            {
                "assistant_id": kwargs["assistant_id"],
                "app_id": "cli_b",
                "app_secret": "sec2",
                "mode": "shared_hermes",
                "user_open_id": None,
            },
        )(),
    )
    assert main(["assistant", "bind", "feishu", "--id", "cdp-bot", "--wizard"]) == 0


def test_cli_assistant_bind_feishu_requires_credentials_without_wizard(evolux_home):
    run_setup(home=evolux_home)
    assert main(["assistant", "bind", "feishu", "--id", "x"]) == 1


def test_cli_assistant_create(evolux_home):
    run_setup(home=evolux_home)
    assert main(["assistant", "create", "--id", "life-bot", "--name", "生活助手"]) == 0
    cfg = AssistantRegistry(home=evolux_home).get("life-bot")
    assert cfg.name == "生活助手"
    assert "cli" in cfg.platforms
