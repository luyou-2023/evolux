"""Install and manage Evolux gateway as a user service (systemd / launchd)."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from evolux_constants import EVOLUX_HOME_ENV, EVOLUX_PROFILE_ENV, get_evolux_home

SERVICE_STEM = "evolux-gateway"


def service_label(profile: str = "") -> str:
    if profile:
        return f"ai.evolux.gateway.{profile}"
    return "ai.evolux.gateway"


def systemd_unit_name(profile: str = "") -> str:
    if profile:
        return f"{SERVICE_STEM}-{profile}.service"
    return f"{SERVICE_STEM}.service"


def resolve_evolux_argv(profile: str = "") -> list[str]:
    exe = shutil.which("evolux")
    argv = [exe] if exe else [sys.executable, "-m", "cli.main"]
    if profile:
        argv.extend(["-p", profile])
    argv.extend(["gateway", "run"])
    return argv


def generate_systemd_unit(*, home: Path, profile: str = "") -> str:
    argv = resolve_evolux_argv(profile)
    unit = systemd_unit_name(profile)
    env_lines = [f"Environment={EVOLUX_HOME_ENV}={home}"]
    if profile:
        env_lines.append(f"Environment={EVOLUX_PROFILE_ENV}={profile}")
    env_block = "\n".join(env_lines)
    exec_start = subprocess.list2cmdline(argv)
    return f"""[Unit]
Description=Evolux Gateway (webhook, dashboard, cron ticker)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
{env_block}
ExecStart={exec_start}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""


def generate_launchd_plist(*, home: Path, profile: str = "") -> str:
    argv = resolve_evolux_argv(profile)
    label = service_label(profile)
    log_dir = home / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = log_dir / "gateway.stdout.log"
    stderr = log_dir / "gateway.stderr.log"
    args_xml = "\n        ".join(f"<string>{part}</string>" for part in argv)
    env_entries = [
        f"<key>{EVOLUX_HOME_ENV}</key><string>{home}</string>",
    ]
    if profile:
        env_entries.append(
            f"<key>{EVOLUX_PROFILE_ENV}</key><string>{profile}</string>"
        )
    env_xml = "\n        ".join(env_entries)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        {args_xml}
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        {env_xml}
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{stdout}</string>
    <key>StandardErrorPath</key>
    <string>{stderr}</string>
</dict>
</plist>
"""


def systemd_unit_path(profile: str = "") -> Path:
    return Path.home() / ".config/systemd/user" / systemd_unit_name(profile)


def launchd_plist_path(profile: str = "") -> Path:
    return Path.home() / "Library/LaunchAgents" / f"{service_label(profile)}.plist"


def platform_kind() -> str:
    system = platform.system()
    if system == "Darwin":
        return "launchd"
    if system == "Linux":
        return "systemd"
    return "unsupported"


def _active_profile() -> str:
    return os.environ.get(EVOLUX_PROFILE_ENV, "").strip()


def _run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def validate_gateway_ready(home: Path) -> int:
    from gateway.webhook_server import AIOHTTP_AVAILABLE
    from gateway.assistant_registry import AssistantRegistry

    if not AIOHTTP_AVAILABLE:
        print("Install gateway dependencies: pip install evolux[gateway]")
        return 1
    registry = AssistantRegistry(home=home)
    feishu_assistants = [item for item in registry.list() if "feishu" in item.platforms]
    if not feishu_assistants:
        print("No Feishu assistants configured.")
        print("Run: evolux assistant bind feishu --id work-bot --app-id <id> --app-secret <secret>")
        return 1
    return 0


def service_installed(profile: str = "") -> bool:
    kind = platform_kind()
    if kind == "systemd":
        return systemd_unit_path(profile).exists()
    if kind == "launchd":
        return launchd_plist_path(profile).exists()
    return False


def install_gateway_service(*, home: Path | None = None, force: bool = False) -> int:
    kind = platform_kind()
    if kind == "unsupported":
        print("Gateway service install is supported on Linux (systemd) and macOS (launchd) only.")
        print("Run in foreground: evolux gateway run")
        return 1

    base = home or get_evolux_home()
    profile = _active_profile()
    if validate_gateway_ready(base) != 0:
        return 1

    if kind == "systemd":
        path = systemd_unit_path(profile)
        if path.exists() and not force:
            print(f"Service already installed: {path}")
            print("Use: evolux gateway install --force")
            return 0
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(generate_systemd_unit(home=base, profile=profile), encoding="utf-8")
        unit = systemd_unit_name(profile)
        _run(["systemctl", "--user", "daemon-reload"])
        _run(["systemctl", "--user", "enable", unit])
        print(f"Installed user systemd unit: {path}")
        print(f"Start with: evolux gateway start")
        print(f"Logs: journalctl --user -u {unit} -f")
        return 0

    path = launchd_plist_path(profile)
    if path.exists() and not force:
        print(f"Service already installed: {path}")
        print("Use: evolux gateway install --force")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_launchd_plist(home=base, profile=profile), encoding="utf-8")
    domain = f"gui/{os.getuid()}"
    _run(["launchctl", "bootout", domain, str(path)], check=False)
    _run(["launchctl", "bootstrap", domain, str(path)], check=False)
    print(f"Installed launchd agent: {path}")
    print("Start with: evolux gateway start")
    print(f"Logs: {base / 'logs' / 'gateway.stderr.log'}")
    return 0


def uninstall_gateway_service() -> int:
    kind = platform_kind()
    profile = _active_profile()
    if kind == "systemd":
        unit = systemd_unit_name(profile)
        _run(["systemctl", "--user", "disable", unit], check=False)
        _run(["systemctl", "--user", "stop", unit], check=False)
        path = systemd_unit_path(profile)
        if path.exists():
            path.unlink()
        _run(["systemctl", "--user", "daemon-reload"], check=False)
        print(f"Removed systemd unit {unit}")
        return 0
    if kind == "launchd":
        path = launchd_plist_path(profile)
        domain = f"gui/{os.getuid()}"
        _run(["launchctl", "bootout", domain, str(path)], check=False)
        if path.exists():
            path.unlink()
        print(f"Removed launchd agent {service_label(profile)}")
        return 0
    print("No service manager on this platform.")
    return 1


def start_gateway_service() -> int:
    kind = platform_kind()
    profile = _active_profile()
    if kind == "systemd":
        unit = systemd_unit_name(profile)
        if not systemd_unit_path(profile).exists():
            print("Gateway service not installed. Run: evolux gateway install")
            print("Or foreground: evolux gateway run")
            return 1
        _run(["systemctl", "--user", "start", unit])
        print(f"Started {unit}")
        return 0
    if kind == "launchd":
        path = launchd_plist_path(profile)
        if not path.exists():
            print("Gateway service not installed. Run: evolux gateway install")
            print("Or foreground: evolux gateway run")
            return 1
        domain = f"gui/{os.getuid()}"
        _run(["launchctl", "bootstrap", domain, str(path)], check=False)
        _run(["launchctl", "kickstart", "-k", f"{domain}/{service_label(profile)}"], check=False)
        print(f"Started {service_label(profile)}")
        return 0
    print("Use foreground mode: evolux gateway run")
    return 1


def stop_gateway_service() -> int:
    kind = platform_kind()
    profile = _active_profile()
    if kind == "systemd":
        unit = systemd_unit_name(profile)
        _run(["systemctl", "--user", "stop", unit], check=False)
        print(f"Stopped {unit}")
        return 0
    if kind == "launchd":
        domain = f"gui/{os.getuid()}"
        _run(["launchctl", "bootout", domain, str(launchd_plist_path(profile))], check=False)
        print(f"Stopped {service_label(profile)}")
        return 0
    return 1


def restart_gateway_service() -> int:
    stop_gateway_service()
    return start_gateway_service()


def status_gateway_service() -> int:
    kind = platform_kind()
    profile = _active_profile()
    base = get_evolux_home()
    print(f"EVOLUX_HOME={base}")
    print(f"Service manager: {kind}")
    if kind == "systemd":
        unit = systemd_unit_name(profile)
        path = systemd_unit_path(profile)
        print(f"Unit file: {path} ({'present' if path.exists() else 'missing'})")
        result = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True,
            text=True,
        )
        state = (result.stdout or result.stderr or "unknown").strip()
        print(f"State: {state}")
        return 0
    if kind == "launchd":
        label = service_label(profile)
        path = launchd_plist_path(profile)
        print(f"Plist: {path} ({'present' if path.exists() else 'missing'})")
        result = subprocess.run(
            ["launchctl", "print", f"gui/{os.getuid()}/{label}"],
            capture_output=True,
            text=True,
        )
        print("State: loaded" if result.returncode == 0 else "State: not loaded")
        return 0
    print("Foreground only: evolux gateway run")
    return 0
