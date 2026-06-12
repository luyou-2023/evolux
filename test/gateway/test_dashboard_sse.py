import json

import pytest
from aiohttp.test_utils import TestClient, TestServer

from agent.llm import MockLLMClient, llm_call_adapter
from agent.routing import RoutingContext, SkillCandidate
from agent.tool_selection import select_tools_for_turn
from gateway.activity import emit_activity, get_activity_bus
from gateway.run import GatewayRunner
from gateway.webhook_server import create_gateway_app
from model_tools import get_tool_definitions
from tools.discover import ensure_tools_loaded


def test_select_tools_for_turn_keeps_orchestrator_and_trims_platform():
    ensure_tools_loaded()
    routing = RoutingContext(
        skill_candidates=[SkillCandidate("git", 0.9, description="git workflows")],
        subagent_candidates=[],
        fused_ranking=[],
        suggested_skills=["git"],
    )
    full = get_tool_definitions(platform="cli", include_mcp=False)
    trimmed = select_tools_for_turn(full, routing, platform="cli", max_tools=20, include_mcp=False)
    names = {item["function"]["name"] for item in trimmed}
    assert "dispatch_subagent" in names
    assert "terminal" in names
    assert len(trimmed) <= 20


def test_activity_bus_publish_and_recent():
    bus = get_activity_bus()
    before = len(bus.recent(500))
    emit_activity("test_event", detail="hello")
    assert len(bus.recent(500)) >= before + 1
    assert bus.recent(1)[-1].kind == "test_event"


@pytest.mark.asyncio
async def test_dashboard_sse_streams_events(evolux_home):
    runner = GatewayRunner(
        home=evolux_home,
        llm_call=llm_call_adapter(MockLLMClient(default_content="ok")),
        send_feishu_reply=False,
    )
    app = create_gateway_app(runner, evolux_home)
    emit_activity("sse_probe", detail="visible")

    async with TestClient(TestServer(app)) as http:
        resp = await http.get("/dashboard/events?once=1")
        assert resp.status == 200
        chunk = await resp.content.read(4096)
        text = chunk.decode("utf-8")
        assert "sse_probe" in text
        probe_line = next(line for line in text.splitlines() if "sse_probe" in line)
        payload = json.loads(probe_line.split("data: ", 1)[1])
        assert payload["kind"] == "sse_probe"
    runner.shutdown()


@pytest.mark.asyncio
async def test_dashboard_sse_filters_by_session_key(evolux_home):
    runner = GatewayRunner(
        home=evolux_home,
        llm_call=llm_call_adapter(MockLLMClient(default_content="ok")),
        send_feishu_reply=False,
    )
    app = create_gateway_app(runner, evolux_home)
    emit_activity("match_event", session_key="orchestrator:default:cli:dm:a", detail="keep")
    emit_activity("skip_event", session_key="orchestrator:default:cli:dm:b", detail="drop")

    async with TestClient(TestServer(app)) as http:
        resp = await http.get(
            "/dashboard/events?once=1&session_key=orchestrator%3Adefault%3Acli%3Adm%3Aa"
        )
        assert resp.status == 200
        text = (await resp.content.read(8192)).decode("utf-8")
        assert "match_event" in text
        assert "skip_event" not in text
    runner.shutdown()
