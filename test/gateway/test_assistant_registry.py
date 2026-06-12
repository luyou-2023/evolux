from gateway.assistant_registry import AssistantRegistry


def test_assistant_registry_loads_from_yaml(evolux_home):
    (evolux_home / "config.yaml").write_text(
        """
assistants:
  work-bot:
    name: 工作助手
    platforms:
      feishu:
        app_id: app1
  life-bot:
    name: 生活助手
    platforms:
      feishu:
        app_id: app2
""".strip(),
        encoding="utf-8",
    )
    registry = AssistantRegistry(home=evolux_home)
    assert len(registry.list()) == 2
    work = registry.get("work-bot")
    assert work is not None
    assert work.platforms["feishu"]["app_id"] == "app1"


def test_assistant_registry_resolve_for_platform(evolux_home):
    (evolux_home / "config.yaml").write_text(
        """
assistants:
  work-bot:
    name: Work
    platforms:
      feishu: {}
  default:
    name: Default
    platforms:
      cli: {}
""".strip(),
        encoding="utf-8",
    )
    registry = AssistantRegistry(home=evolux_home)
    resolved = registry.resolve_for_platform("feishu")
    assert resolved.assistant_id == "work-bot"


def test_assistant_registry_bind_platform(evolux_home):
    registry = AssistantRegistry(home=evolux_home)
    registry.bind_platform("work-bot", "feishu", {"app_id": "cli_app", "mode": "webhook"})
    loaded = AssistantRegistry(home=evolux_home).get("work-bot")
    assert loaded.platforms["feishu"]["app_id"] == "cli_app"
