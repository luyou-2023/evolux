from agent.slash_commands import SlashCommandContext, try_handle_slash_command
from evolux_state import SessionDB


def test_slash_title_set_and_show(evolux_home):
    db = SessionDB(home=evolux_home)
    key = "orchestrator:default:cli:dm:title"
    db.get_or_create_session(key, "default", "cli")
    ctx = SlashCommandContext(
        session_key=key,
        assistant_id="default",
        platform="cli",
        session_db=db,
    )
    set_out = try_handle_slash_command("/title My Project", ctx=ctx)
    show_out = try_handle_slash_command("/title", ctx=ctx)
    assert set_out and "My Project" in (set_out.reply or "")
    assert show_out and "My Project" in (show_out.reply or "")
    assert db.get_session_title(key) == "My Project"


def test_session_db_title_migration(evolux_home):
    db = SessionDB(home=evolux_home)
    session_id = db.create_session("orchestrator:default:cli:dm:t", "default", "cli")
    assert db.set_session_title("orchestrator:default:cli:dm:t", "named") is True
    assert db.get_session_title("orchestrator:default:cli:dm:t") == "named"
    row = db.get_session_row("orchestrator:default:cli:dm:t")
    assert row and row["session_id"] == session_id


def test_slash_skills_browse(evolux_home):
    db = SessionDB(home=evolux_home)
    (evolux_home / "skills" / "demo-skill").mkdir(parents=True)
    (evolux_home / "skills" / "demo-skill" / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Demo skill for tests\n---\n# Demo\n",
        encoding="utf-8",
    )
    outcome = try_handle_slash_command(
        "/skills browse",
        ctx=SlashCommandContext(
            session_key="orchestrator:default:cli:dm:local",
            assistant_id="default",
            platform="cli",
            session_db=db,
            home=evolux_home,
        ),
    )
    assert outcome and outcome.handled
    assert "demo-skill" in (outcome.reply or "")


def test_slash_commands_returns_feishu_card(evolux_home):
    db = SessionDB(home=evolux_home)
    outcome = try_handle_slash_command(
        "/commands",
        ctx=SlashCommandContext(
            session_key="orchestrator:default:cli:dm:local",
            assistant_id="default",
            platform="feishu",
            session_db=db,
        ),
    )
    assert outcome and outcome.interactive_card is not None
    assert outcome.interactive_card["header"]["title"]["content"] == "Evolux 命令参考"
