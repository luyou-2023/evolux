from evolux_state import SessionDB


def test_session_db_create_and_append_message(evolux_home):
    db = SessionDB(home=evolux_home)
    session_id = db.create_session(
        session_key="orchestrator:default:cli:dm:user1",
        assistant_id="default",
        platform="cli",
    )
    db.append_message(session_id, role="user", content="hello")
    db.append_message(session_id, role="assistant", content="hi")
    messages = db.get_messages(session_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["content"] == "hi"


def test_session_db_get_by_session_key(evolux_home):
    db = SessionDB(home=evolux_home)
    key = "orchestrator:work:feishu:dm:chat1"
    session_id = db.create_session(session_key=key, assistant_id="work", platform="feishu")
    loaded_id = db.get_session_id_by_key(key)
    assert loaded_id == session_id
