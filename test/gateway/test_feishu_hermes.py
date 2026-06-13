from gateway.platforms.feishu import feishu_connection_mode, feishu_skips_evolux_transport
from gateway.platforms.feishu_hermes import (
    HERMES_DEFAULT_FEISHU_WEBHOOK_PORT,
    suggest_evolux_gateway_port,
)


def test_feishu_shared_hermes_mode():
    cfg = {"mode": "shared_hermes"}
    assert feishu_connection_mode(cfg) == "shared_hermes"
    assert feishu_skips_evolux_transport(cfg) is True


def test_suggest_evolux_gateway_port_avoids_in_use(monkeypatch):
    monkeypatch.setattr(
        "gateway.platforms.feishu_hermes.is_port_in_use",
        lambda host, port: port == 8787,
    )
    monkeypatch.setattr("gateway.platforms.feishu_hermes.hermes_gateway_running", lambda home=None: False)
    monkeypatch.setattr("gateway.platforms.feishu_hermes.read_hermes_gateway_port", lambda home=None: None)
    assert suggest_evolux_gateway_port(8787) == 8788


def test_hermes_default_feishu_webhook_port():
    assert HERMES_DEFAULT_FEISHU_WEBHOOK_PORT == 8765
