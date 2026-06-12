"""Interactive CLI chat with the orchestrator agent."""

from __future__ import annotations

import sys
from pathlib import Path

from agent.runtime import bootstrap, create_llm_call
from agent.turn_trace import TurnTrace
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
    return base, agent, session_key


def run_chat_once(
    message: str,
    home: Path | None = None,
    assistant_id: str = "default",
    *,
    trace: bool = False,
) -> int:
    _, agent, session_key = _build_chat_agent(home, assistant_id)
    turn_trace = TurnTrace() if trace else None
    result = agent.run_orchestrator_turn(session_key, message, platform="cli", trace=turn_trace)
    if turn_trace:
        render_trace(turn_trace)
    print(result.content or "")
    agent.close()
    return 0


def run_chat(
    home: Path | None = None,
    assistant_id: str = "default",
    *,
    trace: bool = False,
) -> int:
    _, agent, session_key = _build_chat_agent(home, assistant_id)

    print(f"Evolux chat (assistant={assistant_id}). Type /exit to quit.")
    if trace:
        print("Trace mode: orchestration steps print to stderr.", file=sys.stderr)
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
        result = agent.run_orchestrator_turn(session_key, line, platform="cli", trace=turn_trace)
        if turn_trace:
            render_trace(turn_trace)
        print(f"bot> {result.content or '(no response)'}")

    agent.close()
    return 0
