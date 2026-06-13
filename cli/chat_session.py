"""CLI session resume/save messaging (independent from Hermes gateway sessions)."""

from __future__ import annotations

from pathlib import Path

from evolux_state import SessionDB


def cli_session_message_count(session_db: SessionDB, session_key: str) -> int:
    session_id = session_db.get_session_id_by_key(session_key)
    if not session_id:
        return 0
    return session_db.count_messages(session_id)


def format_cli_startup_lines(
    *,
    assistant_id: str,
    session_key: str,
    message_count: int,
    home: Path,
) -> list[str]:
    db_path = home / "state.db"
    header = f"Evolux chat (assistant={assistant_id}). Type /exit to quit."
    if message_count:
        detail = (
            f"Resuming CLI session ({message_count} message(s)) → {session_key}\n"
            f"  persisted: {db_path}\n"
            "  Hermes/Feishu sessions are separate; this process stops when you /exit."
        )
    else:
        detail = (
            f"New CLI session → {session_key}\n"
            f"  persisted: {db_path}\n"
            "  No gateway required; /exit saves and stops this CLI only."
        )
    return [header, detail]


def format_cli_exit_line(home: Path) -> str:
    return f"Session saved to {home / 'state.db'}. CLI stopped."


def format_once_followup_hint(home: Path) -> str:
    return (
        f"Session saved to {home / 'state.db'}. "
        "For multi-turn chat until you quit, run: evolux chat"
    )
