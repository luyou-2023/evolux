"""Interactive CLI chat with the orchestrator agent."""

from __future__ import annotations

import sys
from pathlib import Path

from agent.runtime import bootstrap, create_llm_call
from evolux_constants import get_evolux_home
from evolux_logging import setup_logging
from gateway.session import SessionSource, build_session_key
from run_agent import EvoluxAgent


def run_chat(home: Path | None = None, assistant_id: str = "default") -> int:
    base, settings = bootstrap(home)
    setup_logging(base)
    llm_call = create_llm_call(base, settings)
    agent = EvoluxAgent(llm_call=llm_call, home=base, assistant_id=assistant_id, settings=settings)

    session_key = build_session_key(
        assistant_id,
        SessionSource(platform="cli", chat_type="dm", chat_id="local"),
    )

    print(f"Evolux chat (assistant={assistant_id}). Type /exit to quit.")
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

        result = agent.run_orchestrator_turn(session_key, line, platform="cli")
        print(f"bot> {result.content or '(no response)'}")

    agent.close()
    return 0
