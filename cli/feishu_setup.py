"""Feishu app creation via official lark-oapi register_app (scan URL / QR)."""

from __future__ import annotations

import sys
import webbrowser
from dataclasses import dataclass
from typing import Any, Callable

from gateway.assistant_registry import AssistantRegistry


@dataclass
class FeishuSetupResult:
    assistant_id: str
    app_id: str
    app_secret: str
    mode: str
    user_open_id: str | None = None


RegisterFn = Callable[..., dict[str, Any]]


def feishu_register_app_available() -> bool:
    try:
        import lark_oapi as lark  # noqa: F401

        return hasattr(lark, "register_app")
    except ImportError:
        return False


def resolve_feishu_bind_mode(*, requested: str | None = None, home=None) -> str:
    if requested and requested != "auto":
        return requested
    # Evolux assistants should own Feishu WebSocket by default; shared_hermes delegates
    # replies to Hermes main agent (same session), not the Evolux orchestrator.
    return "websocket"


def _print_qr_prompt(url: str, expire_in: int, *, open_browser: bool) -> None:
    print(f"\n飞书扫码或打开链接创建机器人（{expire_in}s 内有效）:\n  {url}\n")
    try:
        import qrcode

        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        print()
    except ImportError:
        print("Tip: 在飞书 App 扫一扫中打开上方链接；或 pip install qrcode 显示终端二维码。\n")
    if open_browser:
        try:
            webbrowser.open(url)
        except OSError:
            pass


def _default_register_app(**kwargs: Any) -> dict[str, Any]:
    import lark_oapi as lark

    return lark.register_app(**kwargs)


def run_feishu_app_wizard(
    registry: AssistantRegistry,
    *,
    assistant_id: str,
    app_name: str | None = None,
    app_desc: str | None = None,
    mode: str | None = None,
    open_browser: bool = True,
    register_fn: RegisterFn | None = None,
) -> FeishuSetupResult:
    if not feishu_register_app_available():
        raise RuntimeError(
            "Feishu scan setup requires lark-oapi>=1.5.5 with register_app. "
            "Install: pip install 'evolux[gateway]'"
        )

    resolved_mode = resolve_feishu_bind_mode(requested=mode, home=registry.home)
    preset_name = app_name or f"Evolux {assistant_id}"
    preset_desc = app_desc or "Evolux agent bot (auto-created via CLI scan)"
    app_preset = {"name": preset_name, "desc": preset_desc}

    print(f"Creating Feishu app for assistant={assistant_id} (mode={resolved_mode})...")
    print("Waiting for Feishu authorization...", file=sys.stderr)

    register = register_fn or _default_register_app
    result = register(
        on_qr_code=lambda info: _print_qr_prompt(
            str(info["url"]),
            int(info.get("expire_in") or 600),
            open_browser=open_browser,
        ),
        on_status_change=lambda info: print(
            f"  … {info.get('status', 'polling')}",
            file=sys.stderr,
        ),
        source="evolux",
        app_preset=app_preset,
    )

    app_id = str(result["client_id"])
    app_secret = str(result["client_secret"])
    user_info = result.get("user_info") or {}
    user_open_id = str(user_info.get("open_id") or "") or None

    registry.bind_platform(
        assistant_id,
        "feishu",
        {
            "app_id": app_id,
            "app_secret": app_secret,
            "mode": resolved_mode,
        },
    )

    return FeishuSetupResult(
        assistant_id=assistant_id,
        app_id=app_id,
        app_secret=app_secret,
        mode=resolved_mode,
        user_open_id=user_open_id,
    )


def print_feishu_setup_success(result: FeishuSetupResult, *, home) -> None:
    print(f"✓ Feishu bound to assistant `{result.assistant_id}`")
    print(f"  app_id: {result.app_id}")
    print(f"  mode: {result.mode}")
    if result.mode == "shared_hermes":
        print("  Feishu transport: Hermes gateway (Hermes 主 Agent 回复，非 Evolux orchestrator)")
        print("  Tip: 若要用 Evolux 回复，请改用 --mode websocket 并重启 gateway")
    else:
        print("  Next: evolux gateway run")
    print(f"  config: {home / 'config.yaml'}")
