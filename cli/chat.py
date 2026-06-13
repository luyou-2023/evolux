"""Interactive CLI chat with the orchestrator agent."""

from __future__ import annotations

import sys
from pathlib import Path

from agent.runtime import bootstrap, create_llm_call
from agent.turn_trace import TurnTrace
from cli.chat_completion import install_slash_completer
from cli.chat_session import (
    cli_session_message_count,
    format_cli_exit_line,
    format_cli_startup_lines,
    format_once_followup_hint,
)
from cli.trace_render import render_trace
from evolux_constants import get_evolux_home
from evolux_logging import setup_logging
from gateway.session import SessionSource, build_session_key
from run_agent import EvoluxAgent


def _build_chat_agent(home: Path | None, assistant_id: str):
    base, settings = bootstrap(home)
    setup_logging(base)
    llm_call = create_llm_call(base, settings)
    agent = EvoluxAgent(llm_call=llm_call, home=base, assistant_id=assistant_id, settings=settings)
    session_key = build_session_key(
        assistant_id,
        SessionSource(platform="cli", chat_type="dm", chat_id="local"),
    )
    progress_callback = None
    if settings.monitor.push_interim:

        def progress_callback(message: str) -> None:
            print(message, file=sys.stderr)

    return base, agent, session_key, progress_callback


def run_chat_once(
    message: str,
    home: Path | None = None,
    assistant_id: str = "default",
    *,
    trace: bool = False,
) -> int:
    base, agent, session_key, progress_callback = _build_chat_agent(home, assistant_id)
    turn_trace = TurnTrace() if trace else None
    result = agent.run_orchestrator_turn(
        session_key,
        message,
        platform="cli",
        trace=turn_trace,
        progress_callback=progress_callback,
    )
    if turn_trace:
        render_trace(turn_trace)
    print(result.content or "")
    if result.content:
        print(format_once_followup_hint(base), file=sys.stderr)
    agent.close()
    return 0


def run_chat(
    home: Path | None = None,
    assistant_id: str = "default",
    *,
    trace: bool = False,
) -> int:
    base, agent, session_key, progress_callback = _build_chat_agent(home, assistant_id)
    message_count = cli_session_message_count(agent.session_db, session_key)
    for line in format_cli_startup_lines(
        assistant_id=assistant_id,
        session_key=session_key,
        message_count=message_count,
        home=base,
    ):
        print(line)
    if install_slash_completer():
        print("Tip: Tab completes /slash commands.", file=sys.stderr)
    if trace:
        print("Trace mode: orchestration steps print to stderr.", file=sys.stderr)
    elif progress_callback:
        print("Monitor: orchestration progress prints to stderr.", file=sys.stderr)
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in {"/exit", "/quit"}:
            break

        turn_trace = TurnTrace() if trace else None
        result = agent.run_orchestrator_turn(
            session_key,
            line,
            platform="cli",
            trace=turn_trace,
            progress_callback=progress_callback,
        )
        if turn_trace:
            render_trace(turn_trace)
        if getattr(result, "switch_session_key", None):
            session_key = result.switch_session_key
            print(f"bot> {result.content or '(no response)'}")
            print(f"[session → {session_key}]", file=sys.stderr)
            continue
        print(f"bot> {result.content or '(no response)'}")

    print(format_cli_exit_line(base), file=sys.stderr)
    agent.close()
    return 0
