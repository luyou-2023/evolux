from agent.turn_trace import TurnTrace
from gateway.platforms.feishu_format import build_feishu_clarify_card, find_clarify_request


def test_find_clarify_request_from_trace():
    trace = TurnTrace()
    trace.add_tool(
        name="clarify",
        arguments={"question": "Which repo?", "options": ["evolux", "hermes"]},
        result='{"clarify": true, "question": "Which repo?", "options": ["evolux", "hermes"]}',
    )
    payload = find_clarify_request(trace)
    assert payload is not None
    assert payload["question"] == "Which repo?"
    assert payload["options"] == ["evolux", "hermes"]


def test_build_feishu_clarify_card_has_buttons():
    card = build_feishu_clarify_card(
        {"clarify": True, "question": "Pick one", "options": ["A", "B"]}
    )
    assert card["header"]["title"]["content"] == "需要您的确认"
    assert any(item.get("tag") == "action" for item in card["elements"])
