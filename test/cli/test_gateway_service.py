from pathlib import Path

import pytest

from cli.gateway_service import (
    generate_launchd_plist,
    generate_systemd_unit,
    launchd_plist_path,
    platform_kind,
    resolve_evolux_argv,
    service_label,
    systemd_unit_name,
    systemd_unit_path,
    validate_gateway_ready,
)
from cli.main import main
from cli.setup import run_setup
from gateway.assistant_registry import AssistantRegistry


def test_resolve_evolux_argv_includes_run():
    argv = resolve_evolux_argv("")
    assert argv[-2:] == ["gateway", "run"]


def test_generate_systemd_unit_contains_home(evolux_home):
    unit = generate_systemd_unit(home=evolux_home, profile="work")
    assert "EVOLUX_HOME=" in unit
    assert "EVOLUX_PROFILE=work" in unit
    assert "gateway run" in unit
    assert systemd_unit_name("work") == "evolux-gateway-work.service"


def test_generate_launchd_plist(evolux_home):
    plist = generate_launchd_plist(home=evolux_home)
    assert service_label() in plist
    assert "<string>gateway</string>" in plist
    assert "<string>run</string>" in plist
    assert str(evolux_home) in plist


def test_systemd_unit_path():
    assert systemd_unit_path().name == "evolux-gateway.service"
    assert "systemd/user" in str(systemd_unit_path())


def test_launchd_plist_path():
    assert launchd_plist_path().name == "ai.evolux.gateway.plist"


def test_validate_gateway_ready_requires_feishu(evolux_home):
    run_setup(home=evolux_home)
    assert validate_gateway_ready(evolux_home) == 1


def test_validate_gateway_ready_ok(evolux_home):
    run_setup(home=evolux_home)
    main(
        [
            "assistant",
            "bind",
            "feishu",
            "--id",
            "work-bot",
            "--app-id",
            "app1",
            "--app-secret",
            "secret",
            "--mode",
            "webhook",
        ]
    )
    assert validate_gateway_ready(evolux_home) == 0


def test_validate_gateway_ready_websocket_requires_deps(evolux_home, monkeypatch):
    run_setup(home=evolux_home)
    main(
        [
            "assistant",
            "bind",
            "feishu",
            "--id",
            "work-bot",
            "--app-id",
            "app1",
            "--app-secret",
            "secret",
            "--mode",
            "websocket",
        ]
    )
    monkeypatch.setattr("gateway.platforms.feishu_ws.FEISHU_WS_AVAILABLE", False)
    assert validate_gateway_ready(evolux_home) == 1


def test_cli_gateway_run_requires_feishu(evolux_home):
    run_setup(home=evolux_home)
    assert main(["gateway", "run"]) == 1


def test_cli_gateway_run_check(evolux_home):
    run_setup(home=evolux_home)
    main(
        [
            "assistant",
            "bind",
            "feishu",
            "--id",
            "work-bot",
            "--app-id",
            "app1",
            "--mode",
            "webhook",
        ]
    )
    assert main(["gateway", "run", "--check"]) == 0


def test_install_gateway_service_writes_unit(evolux_home, monkeypatch, tmp_path):
    run_setup(home=evolux_home)
    main(
        [
            "assistant",
            "bind",
            "feishu",
            "--id",
            "work-bot",
            "--app-id",
            "app1",
            "--mode",
            "webhook",
        ]
    )
    monkeypatch.setattr("cli.gateway_service.platform_kind", lambda: "systemd")
    unit_path = tmp_path / "evolux-gateway.service"
    monkeypatch.setattr("cli.gateway_service.systemd_unit_path", lambda profile="": unit_path)

    calls = []

    def fake_run(cmd, *, check=True, capture_output=True, text=True):
        calls.append(cmd)
        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("cli.gateway_service._run", fake_run)
    from cli.gateway_service import install_gateway_service

    assert install_gateway_service(home=evolux_home) == 0
    assert unit_path.exists()
    assert "gateway run" in unit_path.read_text(encoding="utf-8")
    assert ["systemctl", "--user", "daemon-reload"] in calls


@pytest.mark.skipif(platform_kind() == "unsupported", reason="needs systemd or launchd")
def test_cli_gateway_status():
    assert main(["gateway", "status"]) in {0, 1}
