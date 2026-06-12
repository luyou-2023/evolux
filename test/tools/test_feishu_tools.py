import json

import yaml

from tools.discover import ensure_tools_loaded
from tools.registry import registry


def _bind_feishu(home):
    config = {
        "assistants": {
            "default": {
                "name": "default",
                "platforms": {"feishu": {"app_id": "app_test", "app_secret": "secret_test"}},
            }
        }
    }
    (home / "config.yaml").write_text(yaml.dump(config), encoding="utf-8")


def test_feishu_message_tool(evolux_home, monkeypatch):
    _bind_feishu(evolux_home)
    ensure_tools_loaded()

    from gateway.platforms.feishu_api import FeishuAPIClient

    def fake_send(self, chat_id, text):
        return {"code": 0, "data": {"message_id": "om_test"}}

    monkeypatch.setattr(FeishuAPIClient, "send_text", fake_send)

    raw = registry.dispatch(
        "feishu_message",
        {"chat_id": "oc_1", "text": "hello"},
        assistant_id="default",
    )
    payload = json.loads(raw)
    assert payload["success"] is True
    assert payload["message_id"] == "om_test"


def test_feishu_doc_read_tool(evolux_home, monkeypatch):
    _bind_feishu(evolux_home)
    ensure_tools_loaded()

    from gateway.platforms.feishu_api import FeishuAPIClient

    def fake_read(self, document_id):
        return {"code": 0, "data": {"content": "doc body"}}

    monkeypatch.setattr(FeishuAPIClient, "read_doc_raw", fake_read)

    raw = registry.dispatch("feishu_doc_read", {"document_id": "doxcn123"}, assistant_id="default")
    payload = json.loads(raw)
    assert payload["success"] is True
    assert payload["content"] == "doc body"
