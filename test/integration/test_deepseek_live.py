import os

import pytest

from agent.llm import create_llm_client
from agent.runtime import create_llm_call
from gateway.session import SessionSource, build_session_key
from run_agent import EvoluxAgent


pytestmark = pytest.mark.live


@pytest.fixture
def deepseek_available():
    if not os.environ.get("DEEPSEEK_API_KEY"):
        pytest.skip("DEEPSEEK_API_KEY not set")


def test_deepseek_client_completes(deepseek_available):
    client = create_llm_client(provider="deepseek")
    response = client.complete([{"role": "user", "content": "Reply with exactly: EVOLUX_OK"}])
    assert response.content
    assert "EVOLUX_OK" in response.content.upper() or len(response.content.strip()) > 0


def test_deepseek_orchestrator_turn(deepseek_available, evolux_home):
    llm_call = create_llm_call(evolux_home)
    agent = EvoluxAgent(llm_call=llm_call, home=evolux_home, assistant_id="default")
    session_key = build_session_key(
        "default",
        SessionSource(platform="cli", chat_type="dm", chat_id="live-test"),
    )
    result = agent.run_orchestrator_turn(session_key, "用一句话介绍 Evolux 是什么。")
    assert result.content
    assert len(result.content.strip()) > 4
    agent.close()


def test_deepseek_chat_once_with_tools(deepseek_available, evolux_home):
    llm_call = create_llm_call(evolux_home)
    agent = EvoluxAgent(llm_call=llm_call, home=evolux_home, assistant_id="default")
    session_key = build_session_key(
        "default",
        SessionSource(platform="cli", chat_type="dm", chat_id="live-tools"),
    )
    result = agent.run_orchestrator_turn(
        session_key,
        "Reply with exactly one word: OK",
        platform="cli",
    )
    assert result.content
    assert "OK" in result.content.upper()
    agent.close()
