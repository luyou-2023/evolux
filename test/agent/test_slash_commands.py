from agent.slash_commands import SlashCommandContext, parse_slash_command, try_handle_slash_command
from evolux_state import SessionDB


def test_parse_slash_command():
    assert parse_slash_command("/help") == ("help", "")
    assert parse_slash_command("/NEW") == ("new", "")
    assert parse_slash_command("/reset") == ("new", "")
    assert parse_slash_command("/history 10") == ("history", "10")
    assert parse_slash_command("hello") is None


def test_slash_help(evolux_home):
    db = SessionDB(home=evolux_home)
    outcome = try_handle_slash_command(
        "/help",
        ctx=SlashCommandContext(
            session_key="orchestrator:default:cli:dm:local",
            assistant_id="default",
            platform="cli",
            session_db=db,
        ),
    )
    assert outcome is not None
    assert outcome.handled is True
    assert "/stop" in (outcome.reply or "")


def test_slash_new_resets_session(evolux_home):
    db = SessionDB(home=evolux_home)
    key = "orchestrator:default:cli:dm:local"
    session_id = db.get_or_create_session(key, "default", "cli")
    db.append_message(session_id, "user", "hello")
    db.append_message(session_id, "assistant", "hi")

    outcome = try_handle_slash_command(
        "/new",
        ctx=SlashCommandContext(
            session_key=key,
            assistant_id="default",
            platform="cli",
            session_db=db,
        ),
    )
    assert outcome and outcome.handled
    new_session_id = db.get_session_id_by_key(key)
    assert new_session_id != session_id
    assert db.count_messages(new_session_id) == 0


def test_slash_undo(evolux_home):
    db = SessionDB(home=evolux_home)
    key = "orchestrator:default:cli:dm:local"
    session_id = db.get_or_create_session(key, "default", "cli")
    db.append_message(session_id, "user", "hello")
    db.append_message(session_id, "assistant", "hi")

    outcome = try_handle_slash_command(
        "/undo",
        ctx=SlashCommandContext(
            session_key=key,
            assistant_id="default",
            platform="cli",
            session_db=db,
        ),
    )
    assert outcome and outcome.handled
    assert db.count_messages(session_id) == 0


def test_slash_retry_reruns_last_message(evolux_home):
    db = SessionDB(home=evolux_home)
    key = "orchestrator:default:cli:dm:local"
    session_id = db.get_or_create_session(key, "default", "cli")
    db.append_message(session_id, "user", "hello")
    db.append_message(session_id, "assistant", "hi")

    outcome = try_handle_slash_command(
        "/retry",
        ctx=SlashCommandContext(
            session_key=key,
            assistant_id="default",
            platform="cli",
            session_db=db,
        ),
    )
    assert outcome and outcome.handled
    assert outcome.rerun_message == "hello"
    assert db.count_messages(session_id) == 0
