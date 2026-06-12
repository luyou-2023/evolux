from gateway.platforms.feishu_format import build_feishu_commands_card


def test_build_feishu_commands_card():
    card = build_feishu_commands_card()
    assert card["header"]["title"]["content"] == "Evolux 命令参考"
    content = str(card["elements"])
    assert "/stop" in content
    assert "/skills browse" in content
    assert "/resume" in content
