import json
from unittest.mock import patch

from tools.discover import ensure_tools_loaded
from tools.registry import registry


def test_web_search_parses_duckduckgo_payload():
    ensure_tools_loaded()
    fake = json.dumps(
        {
            "AbstractText": "Evolux is a multi-agent runtime.",
            "Heading": "Evolux",
            "AbstractURL": "https://example.com",
            "RelatedTopics": [],
        }
    ).encode("utf-8")
    with patch("tools.web_tools._fetch", return_value=fake):
        raw = registry.dispatch("web_search", {"query": "evolux"})
    payload = json.loads(raw)
    assert payload["success"] is True
    assert payload["results"][0]["description"]


def test_web_extract_strips_html():
    ensure_tools_loaded()
    html = b"<html><head><title>Hi</title></head><body><p>Hello world</p></body></html>"
    with patch("tools.web_tools._fetch", return_value=html):
        raw = registry.dispatch("web_extract", {"urls": "https://example.com"})
    payload = json.loads(raw)
    assert payload["success"] is True
    assert "Hello world" in payload["results"][0]["content"]
