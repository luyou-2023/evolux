import json

import yaml

from cli.hermes_detect import discover_hermes_installs, looks_like_hermes
from cli.hermes_migration import migrate_from_hermes


def _write_hermes_home(path):
    path.mkdir(parents=True)
    (path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "model": "deepseek/deepseek-chat",
                "providers": {
                    "deepseek": {
                        "enabled": True,
                        "model": "deepseek-chat",
                        "base_url": "https://api.deepseek.com",
                    }
                },
                "mcp_servers": {
                    "echo": {"command": "echo", "args": ["hi"]},
                },
                "cron": {
                    "jobs": [
                        {
                            "id": "heartbeat",
                            "interval_seconds": 3600,
                            "prompt": "ping",
                            "enabled": True,
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (path / "memories").mkdir()
    (path / "memories" / "MEMORY.md").write_text("§ test memory\n", encoding="utf-8")
    (path / "memories" / "USER.md").write_text("§ user pref\n", encoding="utf-8")
    (path / "skills" / "demo").mkdir(parents=True)
    (path / "skills" / "demo" / "SKILL.md").write_text("---\nname: demo\n---\n", encoding="utf-8")
    (path / ".env").write_text("DEEPSEEK_API_KEY=secret\n", encoding="utf-8")
    (path / "state.db").write_bytes(b"sqlite")


def test_looks_like_hermes_and_detect(tmp_path, monkeypatch):
    hermes = tmp_path / "hermes"
    _write_hermes_home(hermes)
    assert looks_like_hermes(hermes)

    monkeypatch.setenv("HERMES_HOME", str(hermes))
    report = discover_hermes_installs()
    assert report.found
    assert report.installs[0].path == hermes.resolve()
    assert report.installs[0].has_memories


def test_migrate_from_hermes_user_data(evolux_home, tmp_path):
    hermes = tmp_path / "hermes"
    _write_hermes_home(hermes)

    result = migrate_from_hermes(hermes, evolux_home, preset="user-data", dry_run=False)

    assert (evolux_home / "memories" / "MEMORY.md").exists()
    assert (evolux_home / "skills" / "demo" / "SKILL.md").exists()
    assert (evolux_home / "config.yaml").exists()
    assert "mcp_servers" in yaml.safe_load((evolux_home / "config.yaml").read_text(encoding="utf-8"))
    assert not (evolux_home / ".env").exists()
    assert result.backup_dir is not None
    assert (result.backup_dir / "state.db").exists()

    store_jobs = json.loads((evolux_home / "cron" / "jobs.json").read_text(encoding="utf-8"))
    assert len(store_jobs) == 1


def test_migrate_from_hermes_full_imports_env(evolux_home, tmp_path):
    hermes = tmp_path / "hermes"
    _write_hermes_home(hermes)

    migrate_from_hermes(hermes, evolux_home, preset="full", dry_run=False)
    assert "DEEPSEEK_API_KEY=secret" in (evolux_home / ".env").read_text(encoding="utf-8")


def test_migrate_upgrades_feishu_assistants_to_websocket(evolux_home, tmp_path):
    hermes = tmp_path / "hermes"
    _write_hermes_home(hermes)
    hermes_cfg = yaml.safe_load((hermes / "config.yaml").read_text(encoding="utf-8"))
    hermes_cfg["assistants"] = {
        "cdp-automation": {
            "name": "CDP自动化",
            "platforms": {
                "feishu": {
                    "app_id": "cli_test",
                    "app_secret": "secret",
                    "mode": "webhook",
                }
            },
        }
    }
    (hermes / "config.yaml").write_text(yaml.safe_dump(hermes_cfg), encoding="utf-8")

    migrate_from_hermes(hermes, evolux_home, dry_run=False)
    cfg = yaml.safe_load((evolux_home / "config.yaml").read_text(encoding="utf-8"))
    assert cfg["assistants"]["cdp-automation"]["platforms"]["feishu"]["mode"] == "websocket"


def test_migrate_dry_run(evolux_home, tmp_path):
    hermes = tmp_path / "hermes"
    _write_hermes_home(hermes)

    result = migrate_from_hermes(hermes, evolux_home, dry_run=True)
    assert result.dry_run is True
    assert not (evolux_home / "memories" / "MEMORY.md").exists()
