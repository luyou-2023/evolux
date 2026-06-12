from agent.settings import load_settings


def test_load_settings_defaults(evolux_home):
    settings = load_settings(evolux_home)
    assert settings.orchestrator_max_iterations == 30
    assert settings.compression.keep_recent_turns == 10


def test_load_settings_from_yaml(evolux_home):
    (evolux_home / "config.yaml").write_text(
        "orchestrator:\n  max_iterations: 25\ncompression:\n  keep_recent_turns: 8\n",
        encoding="utf-8",
    )
    settings = load_settings(evolux_home)
    assert settings.orchestrator_max_iterations == 25
    assert settings.compression.keep_recent_turns == 8
