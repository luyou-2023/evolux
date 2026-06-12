from gateway.platforms.feishu import (
    build_feishu_text_reply,
    parse_feishu_webhook,
    verify_feishu_signature,
)


def test_parse_feishu_url_verification():
    result = parse_feishu_webhook(
        {"type": "url_verification", "challenge": "abc"},
        assistant_id="work-bot",
    )
    assert result == {"challenge": "abc"}


def test_parse_feishu_message_event():
    payload = {
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": "ou_x", "union_id": "on_x"}},
            "message": {
                "message_id": "om_1",
                "chat_id": "oc_1",
                "chat_type": "p2p",
                "content": '{"text":"你好"}',
            },
        },
    }
    event = parse_feishu_webhook(payload, assistant_id="work-bot")
    assert event.text == "你好"
    assert event.source.platform == "feishu"
    assert event.source.chat_type == "dm"
    assert event.assistant_id == "work-bot"


def test_build_feishu_text_reply():
    reply = build_feishu_text_reply("oc_1", "hello")
    assert reply["receive_id"] == "oc_1"
    assert "hello" in reply["content"]


def test_verify_feishu_signature():
    body = b'{"ok":true}'
    assert verify_feishu_signature("1", "2", body, "", "anything") is True
