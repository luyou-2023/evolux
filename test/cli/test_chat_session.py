from cli.chat_session import (
    cli_session_message_count,
    format_cli_exit_line,
    format_cli_startup_lines,
    format_once_followup_hint,
)
from evolux_state import SessionDB


def test_count_messages(evolux_home):
    db = SessionDB(home=evolux_home)
    key = "orchestrator:default:cli:dm:local"
    assert cli_session_message_count(db, key) == 0
    session_id = db.get_or_create_session(key, "default", "cli")
    db.append_message(session_id, "user", "hi")
    db.append_message(session_id, "assistant", "hello")
    assert cli_session_message_count(db, key) == 2


def test_format_cli_startup_new_session(evolux_home):
    lines = format_cli_startup_lines(
        assistant_id="default",
        session_key="orchestrator:default:cli:dm:local",
        message_count=0,
        home=evolux_home,
    )
    assert "New CLI session" in lines[1]
    assert "No gateway required" in lines[1]


def test_format_cli_startup_resume(evolux_home):
    lines = format_cli_startup_lines(
        assistant_id="default",
        session_key="orchestrator:default:cli:dm:local",
        message_count=4,
        home=evolux_home,
    )
    assert "Resuming CLI session (4 message(s))" in lines[1]
    assert "Hermes/Feishu sessions are separate" in lines[1]


def test_format_cli_exit_line(evolux_home):
    assert "state.db" in format_cli_exit_line(evolux_home)


def test_format_once_followup_hint(evolux_home):
    hint = format_once_followup_hint(evolux_home)
    assert "evolux chat" in hint
