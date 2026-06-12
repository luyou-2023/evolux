from agent.llm import LLMResponse, MockLLMClient, ToolCall, llm_call_adapter


def test_mock_llm_client_returns_default():
    client = MockLLMClient(default_content="hello")
    response = client.complete([{"role": "user", "content": "hi"}])
    assert response.content == "hello"
    assert len(client.calls) == 1


def test_llm_call_adapter_exposes_tool_calls():
    client = MockLLMClient(
        responses=[
            LLMResponse(
                content=None,
                tool_calls=[ToolCall(id="1", name="echo", arguments={"message": "x"})],
            )
        ]
    )
    call = llm_call_adapter(client)
    result = call([{"role": "user", "content": "run echo"}])
    assert result.content is None
    assert result.tool_calls[0]["name"] == "echo"


def test_create_llm_client_uses_mock_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("EVOLUX_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    from agent.llm import MockLLMClient, create_llm_client

    client = create_llm_client(provider="deepseek", api_key=None)
    assert isinstance(client, MockLLMClient)


def test_resolve_api_key_prefers_deepseek_env(monkeypatch):
    from agent.llm import resolve_api_key

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert resolve_api_key("deepseek") == "sk-test"


def test_resolve_provider_defaults_deepseek():
    from agent.llm import resolve_provider_defaults

    model, base_url = resolve_provider_defaults("deepseek")
    assert model == "deepseek-chat"
    assert base_url == "https://api.deepseek.com"
