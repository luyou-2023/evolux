import json

from gateway.platforms.feishu_api import FeishuAPIClient, FeishuCredentials


def test_feishu_client_gets_token_and_sends_message():
    calls: list[tuple[str, dict[str, str], bytes]] = []

    def fake_post(url: str, headers: dict[str, str], data: bytes) -> dict:
        calls.append((url, headers, data))
        if "tenant_access_token" in url:
            return {"code": 0, "tenant_access_token": "t-token", "expire": 7200}
        payload = json.loads(data.decode("utf-8"))
        assert payload["msg_type"] == "text"
        assert headers["Authorization"] == "Bearer t-token"
        return {"code": 0, "data": {"message_id": "om_1"}}

    client = FeishuAPIClient(
        credentials=FeishuCredentials(app_id="app", app_secret="secret"),
    )
    client._http_post = fake_post

    token = client.get_tenant_access_token()
    assert token == "t-token"
    result = client.send_text("oc_chat", "hello feishu")
    assert result["data"]["message_id"] == "om_1"
    assert len(calls) == 2


def test_build_feishu_client_requires_credentials():
    from gateway.platforms.feishu_api import build_feishu_client

    assert build_feishu_client({}) is None
    client = build_feishu_client({"app_id": "a", "app_secret": "b"})
    assert client is not None
