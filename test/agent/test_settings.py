from agent.settings import load_settings


def test_load_settings_defaults(evolux_home):
    settings = load_settings(evolux_home)
    assert settings.orchestrator_max_iterations == 30
    assert settings.orchestrator_max_concurrent_subagents == 3
    assert settings.compression.keep_recent_turns == 10
    assert settings.vector.backend == "sqlite-vec"
    assert settings.sedimentation.enabled is True
    assert settings.sedimentation.memory_after_turn is True


def test_load_settings_from_yaml(evolux_home):
    (evolux_home / "config.yaml").write_text(
        """
orchestrator:
  max_iterations: 25
  max_concurrent_subagents: 2
compression:
  keep_recent_turns: 8
sedimentation:
  enabled: false
gateway:
  port: 9999
llm:
  provider: deepseek
  model: deepseek-chat
""".strip(),
        encoding="utf-8",
    )
    settings = load_settings(evolux_home)
    assert settings.orchestrator_max_iterations == 25
    assert settings.orchestrator_max_concurrent_subagents == 2
    assert settings.compression.keep_recent_turns == 8
    assert settings.gateway.port == 9999
    assert settings.llm.provider == "deepseek"
    assert settings.llm.model == "deepseek-chat"
    assert settings.sedimentation.enabled is False
