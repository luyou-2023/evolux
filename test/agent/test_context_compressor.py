from agent.context_compressor import CompressionConfig, compress_messages


def test_compress_messages_keeps_recent_ten_turns():
    messages = [{"role": "system", "content": "sys"}]
    for i in range(15):
        messages.append({"role": "user", "content": f"u{i}"})
        messages.append({"role": "assistant", "content": f"a{i}"})

    result = compress_messages(messages, CompressionConfig(keep_recent_turns=10))
    assert result.compressed is True
    assert result.summary is not None
    assert result.messages[-2]["content"] == "u14"
    assert result.messages[-1]["content"] == "a14"
    assert "历史摘要" in result.messages[1]["content"]


def test_compress_messages_skips_when_under_limit():
    messages = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
    ]
    result = compress_messages(messages, CompressionConfig(keep_recent_turns=10))
    assert result.compressed is False
