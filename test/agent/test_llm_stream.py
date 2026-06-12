import json

from agent.llm import LLMResponse, OpenAICompatibleClient


def test_stream_complete_parses_sse_deltas():
    lines = [
        b'data: {"choices":[{"delta":{"content":"Hel"}}]}\n',
        b'data: {"choices":[{"delta":{"content":"lo"}}]}\n',
        b"data: [DONE]\n",
    ]

    class FakeResponse:
        def __init__(self):
            self._lines = list(lines)

        def __iter__(self):
            return iter(self._lines)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    deltas: list[str] = []

    def fake_urlopen(request, timeout):
        return FakeResponse()

    client = OpenAICompatibleClient(api_key="test-key")
    import agent.llm as llm_mod

    original = llm_mod._urlopen
    llm_mod._urlopen = fake_urlopen
    try:
        response = client.stream_complete(
            [{"role": "user", "content": "hi"}],
            on_delta=deltas.append,
        )
    finally:
        llm_mod._urlopen = original

    assert response.content == "Hello"
    assert deltas == ["Hel", "lo"]
