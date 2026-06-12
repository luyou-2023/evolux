"""Terminal UI for Evolux status and quick actions."""

from __future__ import annotations

import sys
from pathlib import Path

from agent.settings import load_settings
from evolux_constants import get_evolux_home
from evolux_state import SessionDB
from gateway.assistant_registry import AssistantRegistry


def run_tui(home: Path | None = None) -> int:
    base = home or get_evolux_home()
    settings = load_settings(base)
    registry = AssistantRegistry(home=base)

    while True:
        print("\n=== Evolux TUI ===")
        print(f"Home: {base}")
        print(f"Gateway: http://{settings.gateway.host}:{settings.gateway.port}")
        print(f"Dashboard: http://{settings.gateway.host}:{settings.gateway.port}/dashboard")
        print("\n1) List assistants")
        print("2) List recent sessions")
        print("3) View session messages")
        print("4) Show config summary")
        print("q) Quit")
        choice = input("\nSelect> ").strip().lower()

        if choice in {"q", "quit", "exit"}:
            return 0
        if choice == "1":
            _show_assistants(registry)
        elif choice == "2":
            _show_sessions(base)
        elif choice == "3":
            _show_session_detail(base)
        elif choice == "4":
            _show_config(settings, registry)
        else:
            print("Unknown option.")


def _show_assistants(registry: AssistantRegistry) -> None:
    items = registry.list()
    if not items:
        print("No assistants configured.")
        return
    for item in items:
        platforms = ", ".join(item.platforms.keys()) or "-"
        print(f"- {item.assistant_id}: {item.name} [{platforms}]")


def _show_sessions(home: Path) -> None:
    db = SessionDB(home=home)
    sessions = db.list_sessions(limit=20)
    db.close()
    if not sessions:
        print("No sessions yet.")
        return
    for item in sessions:
        print(
            f"- {item['session_key']} | assistant={item['assistant_id']} "
            f"| msgs={item['message_count']} | {item['created_at']}"
        )


def _show_session_detail(home: Path) -> None:
    session_key = input("Session key> ").strip()
    if not session_key:
        return
    db = SessionDB(home=home)
    session_id = db.get_session_id_by_key(session_key)
    if not session_id:
        db.close()
        print("Session not found.")
        return
    messages = db.get_messages(session_id)
    db.close()
    for msg in messages:
        print(f"[{msg['role']}] {msg['content']}")


def _show_config(settings, registry: AssistantRegistry) -> None:
    print(f"Orchestrator max iterations: {settings.orchestrator_max_iterations}")
    print(f"Subagent max iterations: {settings.subagent_max_iterations}")
    print(f"LLM provider: {settings.llm.provider} / {settings.llm.model}")
    print(f"MCP servers: {len(settings.mcp.servers)}")
    print(f"Assistants: {len(registry.list())}")


if __name__ == "__main__":
    raise SystemExit(run_tui())
