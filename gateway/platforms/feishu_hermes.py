"""Detect Hermes Feishu ownership for coexistence (shared port / app lock)."""

from __future__ import annotations

import hashlib
import json
import os
import socket
from pathlib import Path
from typing import Any

from cli.hermes_detect import discover_hermes_installs, get_default_hermes_home

HERMES_FEISHU_LOCK_SCOPE = "feishu-app-id"
HERMES_DEFAULT_FEISHU_WEBHOOK_PORT = 8765
HERMES_DEFAULT_FEISHU_WEBHOOK_PATH = "/feishu/webhook"
HERMES_DEFAULT_GATEWAY_PORT = 8787
EVOLUX_FALLBACK_GATEWAY_PORT = 8788


def _scope_hash(identity: str) -> str:
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def hermes_lock_dir() -> Path:
    override = os.getenv("HERMES_GATEWAY_LOCK_DIR")
    if override:
        return Path(override).expanduser()
    state_home = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return state_home / "hermes" / "gateway-locks"


def hermes_feishu_lock_path(app_id: str) -> Path:
    return hermes_lock_dir() / f"{HERMES_FEISHU_LOCK_SCOPE}-{_scope_hash(app_id)}.lock"


def read_hermes_feishu_lock(app_id: str) -> dict[str, Any] | None:
    """Return lock record if Hermes (or another gateway) holds the Feishu app_id."""
    path = hermes_feishu_lock_path(app_id)
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"pid": None, "stale": True}
    return raw if isinstance(raw, dict) else None


def hermes_feishu_app_lock_held(app_id: str, *, skip_pid: int | None = None) -> tuple[bool, dict[str, Any] | None]:
    """True when another live process holds the Hermes Feishu app lock."""
    record = read_hermes_feishu_lock(app_id)
    if not record:
        return False, None
    pid = record.get("pid")
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False, record
    if skip_pid is not None and pid_int == skip_pid:
        return False, record
    try:
        os.kill(pid_int, 0)
    except OSError:
        return False, record
    return True, record


def hermes_gateway_pid(home: Path | None = None) -> int | None:
    base = home or get_default_hermes_home()
    pid_path = base / "gateway.pid"
    if not pid_path.exists():
        return None
    try:
        raw = json.loads(pid_path.read_text(encoding="utf-8"))
        pid = int(raw.get("pid"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return pid


def hermes_gateway_running(home: Path | None = None) -> bool:
    return hermes_gateway_pid(home) is not None


def read_hermes_gateway_port(home: Path | None = None) -> int | None:
    import yaml

    base = home or get_default_hermes_home()
    config_path = base / "config.yaml"
    if not config_path.exists():
        return None
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except OSError:
        return None
    gateway = raw.get("gateway") if isinstance(raw, dict) else None
    if not isinstance(gateway, dict):
        return None
    port = gateway.get("port")
    try:
        return int(port)
    except (TypeError, ValueError):
        return None


def is_port_in_use(host: str, port: int) -> bool:
    if port <= 0:
        return False
    bind_host = host if host not in {"", "0.0.0.0"} else "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((bind_host, port))
        except OSError:
            return True
    return False


def suggest_evolux_gateway_port(preferred: int, *, home: Path | None = None) -> int:
    """Pick a gateway port that avoids Hermes defaults and local bind conflicts."""
    hermes_port = read_hermes_gateway_port()
    candidates = [preferred]
    if hermes_port and hermes_port not in candidates:
        candidates.append(hermes_port)
    if HERMES_DEFAULT_GATEWAY_PORT not in candidates:
        candidates.append(HERMES_DEFAULT_GATEWAY_PORT)
    if EVOLUX_FALLBACK_GATEWAY_PORT not in candidates:
        candidates.append(EVOLUX_FALLBACK_GATEWAY_PORT)

    for port in candidates:
        if hermes_gateway_running() and hermes_port == port:
            continue
        if is_port_in_use("127.0.0.1", port):
            continue
        return port

    for offset in range(1, 20):
        port = preferred + offset
        if not is_port_in_use("127.0.0.1", port):
            return port
    return preferred


def any_hermes_install_running() -> bool:
    report = discover_hermes_installs()
    for install in report.installs:
        if hermes_gateway_running(install.path):
            return True
    return False
