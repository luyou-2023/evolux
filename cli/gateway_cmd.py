"""Gateway CLI commands."""

from __future__ import annotations

from pathlib import Path

from evolux_constants import get_evolux_home
from gateway.assistant_registry import AssistantRegistry


def run_gateway_start(home: Path | None = None) -> int:
    base = home or get_evolux_home()
    registry = AssistantRegistry(home=base)
    feishu_assistants = [item for item in registry.list() if "feishu" in item.platforms]
    if not feishu_assistants:
        print("No Feishu assistants configured.")
        print("Run: evolux assistant bind feishu --id work-bot --app-id <id> --app-secret <secret>")
        return 1

    print("Evolux gateway ready (Phase 3 skeleton).")
    for item in feishu_assistants:
        cfg = item.platforms["feishu"]
        print(f"- {item.assistant_id}: mode={cfg.get('mode', 'webhook')} app_id={cfg.get('app_id', '')}")
    print("Webhook server wiring lands in Phase 3.1 follow-up.")
    return 0
