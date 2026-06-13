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


def test_slash_compress_reduces_messages(evolux_home):
    db = SessionDB(home=evolux_home)
    key = "orchestrator:default:cli:dm:compress"
    session_id = db.get_or_create_session(key, "default", "cli")
    for index in range(12):
        db.append_message(session_id, "user", f"question {index}")
        db.append_message(session_id, "assistant", f"answer {index}")

    from agent.settings import Settings

    outcome = try_handle_slash_command(
        "/compress auth flow",
        ctx=SlashCommandContext(
            session_key=key,
            assistant_id="default",
            platform="cli",
            session_db=db,
            settings=Settings(),
        ),
    )
    assert outcome and outcome.handled
    assert "压缩" in (outcome.reply or "")
    assert "压缩链" in (outcome.reply or "")
    new_session_id = db.get_session_id_by_key(key)
    assert new_session_id is not None
    assert new_session_id != session_id
    assert db.count_messages(new_session_id) < 24
    messages = db.get_messages(new_session_id)
    assert any("auth flow" in str(item["content"]) for item in messages)
    assert db.get_compression_log_for_child(new_session_id) is not None


def test_slash_sessions_lists_current(evolux_home):
    db = SessionDB(home=evolux_home)
    key = "orchestrator:default:cli:dm:s1"
    db.get_or_create_session(key, "default", "cli")
    outcome = try_handle_slash_command(
        "/sessions",
        ctx=SlashCommandContext(
            session_key=key,
            assistant_id="default",
            platform="cli",
            session_db=db,
        ),
    )
    assert outcome and outcome.handled
    assert "当前" in (outcome.reply or "")
    assert key in (outcome.reply or "")


def test_slash_model_and_tools(evolux_home):
    db = SessionDB(home=evolux_home)
    from agent.settings import Settings

    ctx = SlashCommandContext(
        session_key="orchestrator:default:cli:dm:local",
        assistant_id="default",
        platform="cli",
        session_db=db,
        settings=Settings(),
    )
    model = try_handle_slash_command("/model", ctx=ctx)
    tools = try_handle_slash_command("/tools", ctx=ctx)
    assert model and "deepseek" in (model.reply or "")
    assert tools and "可用工具" in (tools.reply or "")
