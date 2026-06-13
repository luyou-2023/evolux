from pathlib import Path

import pytest

from cli.gateway_service import (
    generate_launchd_plist,
    generate_systemd_unit,
    launchd_plist_path,
    platform_kind,
    resolve_evolux_argv,
    service_label,
    service_unit_stale,
    systemd_unit_name,
    systemd_unit_path,
    validate_gateway_ready,
)
from cli.main import main
from cli.setup import run_setup
from gateway.assistant_registry import AssistantRegistry


def test_service_unit_stale_detects_missing_foreground(evolux_home, tmp_path, monkeypatch):
    monkeypatch.setattr("cli.gateway_service.launchd_plist_path", lambda profile="": tmp_path / "a.plist")
    path = tmp_path / "a.plist"
    path.write_text("<string>gateway</string><string>run</string>", encoding="utf-8")
    assert service_unit_stale() is True
    path.write_text("<string>run</string><string>--foreground</string>", encoding="utf-8")
    assert service_unit_stale() is False


def test_resolve_evolux_argv_uses_absolute_path(monkeypatch, tmp_path):
    fake = tmp_path / "evolux"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("cli.gateway_service.shutil.which", lambda name: str(fake))
    argv = resolve_evolux_argv("")
    assert argv[0] == str(fake.resolve())
    assert argv[-3:] == ["gateway", "run", "--foreground"]


def test_generate_systemd_unit_contains_home(evolux_home):
    unit = generate_systemd_unit(home=evolux_home, profile="work")
    assert "EVOLUX_HOME=" in unit
    assert "EVOLUX_PROFILE=work" in unit
    assert "gateway run" in unit
    assert "--foreground" in unit
    assert "PATH=" in unit
    assert systemd_unit_name("work") == "evolux-gateway-work.service"


def test_generate_launchd_plist(evolux_home):
    plist = generate_launchd_plist(home=evolux_home)
    assert service_label() in plist
    assert "<string>gateway</string>" in plist
    assert "<string>run</string>" in plist
    assert "<string>--foreground</string>" in plist
    assert "<key>PATH</key>" in plist
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
            "--app-secret",
            "sec1",
            "--mode",
            "webhook",
        ]
    )
    assert main(["gateway", "run", "--check"]) == 0


def test_cli_gateway_run_starts_background(evolux_home, monkeypatch):
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
            "sec1",
            "--mode",
            "shared_hermes",
        ]
    )
    monkeypatch.setattr("cli.gateway_cmd.run_gateway_background", lambda home=None: 0)
    assert main(["gateway", "run"]) == 0


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
            "--app-secret",
            "sec1",
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
    assert "--foreground" in unit_path.read_text(encoding="utf-8")
    assert ["systemctl", "--user", "daemon-reload"] in calls


@pytest.mark.skipif(platform_kind() == "unsupported", reason="needs systemd or launchd")
def test_cli_gateway_status():
    assert main(["gateway", "status"]) in {0, 1}
