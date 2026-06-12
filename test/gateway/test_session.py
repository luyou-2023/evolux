from gateway.session import SessionSource, build_session_key


def test_build_session_key_includes_assistant_id():
    source = SessionSource(platform="feishu", chat_type="dm", chat_id="chat1", user_id="ou_user")
    key = build_session_key("work-bot", source)
    assert key.startswith("orchestrator:work-bot:feishu:dm:")
    assert "chat1" in key
    assert key.endswith("ou_user")


def test_build_session_key_group_shared_without_user():
    source = SessionSource(platform="feishu", chat_type="group", chat_id="group1")
    key = build_session_key("default", source, group_sessions_per_user=False)
    assert key == "orchestrator:default:feishu:group:group1"
