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


def test_session_db_list_sessions(evolux_home):
    db = SessionDB(home=evolux_home)
    db.create_session("orchestrator:default:cli:dm:a", "default", "cli")
    db.create_session("orchestrator:work:feishu:dm:b", "work", "feishu")
    all_sessions = db.list_sessions(limit=10)
    assert len(all_sessions) == 2
    work_sessions = db.list_sessions(assistant_id="work", limit=10)
    assert len(work_sessions) == 1
    assert work_sessions[0]["assistant_id"] == "work"


def test_session_db_reset_and_pop_exchange(evolux_home):
    db = SessionDB(home=evolux_home)
    key = "orchestrator:default:cli:dm:x"
    session_id = db.create_session(key, "default", "cli")
    db.append_message(session_id, "user", "one")
    db.append_message(session_id, "assistant", "two")
    assert db.count_messages(session_id) == 2
    assert db.pop_last_exchange(session_id) is True
    assert db.count_messages(session_id) == 0
    new_id = db.reset_session(key, "default", "cli")
    assert new_id != session_id
    assert db.get_last_user_message(new_id) is None
