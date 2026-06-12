from gateway.platforms.feishu import (
    build_card_action_ack,
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


def test_parse_feishu_card_action_trigger():
    payload = {
        "schema": "2.0",
        "header": {"event_type": "card.action.trigger"},
        "event": {
            "operator": {"open_id": "ou_card", "union_id": "on_card"},
            "action": {
                "tag": "button",
                "value": {
                    "action": "clarify",
                    "option": "evolux",
                    "question": "Which repo?",
                },
            },
            "context": {
                "open_chat_id": "oc_card",
                "open_message_id": "om_card",
                "chat_type": "p2p",
            },
        },
    }
    event = parse_feishu_webhook(payload, assistant_id="work-bot")
    assert event.is_card_action is True
    assert event.card_action_option == "evolux"
    assert event.card_action_question == "Which repo?"
    assert event.text == "[确认] Which repo? → evolux"
    assert event.source.chat_id == "oc_card"
    assert event.source.user_id == "ou_card"
    assert event.source.chat_type == "dm"


def test_build_card_action_ack():
    ack = build_card_action_ack("已选择：evolux")
    assert ack["toast"]["type"] == "success"
    assert ack["toast"]["content"] == "已选择：evolux"


def test_build_card_action_ack_with_card():
    card = {"header": {"title": {"content": "已确认"}}}
    ack = build_card_action_ack("ok", card=card)
    assert ack["card"]["type"] == "raw"
    assert ack["card"]["data"] == card


def test_verify_feishu_signature():
    body = b'{"ok":true}'
    assert verify_feishu_signature("1", "2", body, "", "anything") is True
