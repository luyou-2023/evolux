"""Interactive setup and default config bootstrap."""

from __future__ import annotations

from pathlib import Path

from evolux_constants import get_evolux_home

DEFAULT_CONFIG = """orchestrator:
  max_iterations: 30
  max_concurrent_subagents: 3

subagent:
  max_iterations: 90

compression:
  keep_recent_turns: 10

routing:
  fusion:
    vector_weight: 0.5
    skill_overlap_weight: 0.4
    recency_weight: 0.1
  skill_identify:
    top_k: 5
    enable_keyword: true
    enable_vector: true

llm:
  provider: deepseek
  model: deepseek-chat
  base_url: https://api.deepseek.com

gateway:
  host: 0.0.0.0
  port: 8787
  feishu_webhook_host: 127.0.0.1
  feishu_webhook_port: 8765
  hermes_compat: true

mcp:
  discover_on_startup: false

mcp_servers: {}

sedimentation:
  enabled: true
  memory_after_turn: true
  llm_extract: false

expert_promotion:
  enabled: true
  min_repeat: 2
  auto_create: true
  score_threshold: 0.35

assistants:
  default:
    name: 默认助手
    platforms:
      cli: {}
"""


def run_setup(
    home: Path | None = None,
    *,
    from_hermes: bool = False,
    skip_hermes: bool = False,
    hermes_preset: str = "user-data",
    yes: bool = False,
) -> int:
    base = home or get_evolux_home()
    base.mkdir(parents=True, exist_ok=True)
    for sub in ("skills", "memories", "agents", "vector", "logs", "state", "cron", "migration"):
        (base / sub).mkdir(parents=True, exist_ok=True)

    registry = base / "agents" / "registry.json"
    if not registry.exists():
        registry.write_text("{}\n", encoding="utf-8")

    _seed_bundled_skills(base)

    config_path = base / "config.yaml"
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"Created {config_path}")
    else:
        print(f"Config already exists: {config_path}")

    if not skip_hermes:
        _maybe_migrate_hermes(
            base,
            auto=from_hermes,
            preset=hermes_preset,
            yes=yes,
        )

    print(f"EVOLUX_HOME={base}")
    print("Put API keys in ~/.evolux/.env (DEEPSEEK_API_KEY, OPENAI_API_KEY, …)")
    return 0


def _maybe_migrate_hermes(
    target: Path,
    *,
    auto: bool,
    preset: str,
    yes: bool,
) -> None:
    from cli.hermes_detect import discover_hermes_installs, format_detect_report, pick_default_source
    from cli.hermes_migration import migrate_from_hermes

    report = discover_hermes_installs()
    if not report.found:
        return

    print(format_detect_report(report))
    source = pick_default_source(report)
    if source is None:
        return

    if not auto and not yes:
        try:
            answer = input(f"Import Hermes sediment from {source}? [Y/n]: ").strip().lower()
        except EOFError:
            return
        if answer in {"n", "no"}:
            print("Skipped Hermes migration.")
            return

    result = migrate_from_hermes(source, target, preset=preset, dry_run=False)
    for line in result.summary_lines():
        print(line)
    print("Run: evolux skills reindex")


def _seed_bundled_skills(home: Path) -> None:
    import shutil
    from pathlib import Path as P

    bundled_roots = [
        P(__file__).resolve().parents[1] / "skills" / "bundled",
        P(__file__).resolve().parents[1] / "skills" / "official",
    ]
    target_root = home / "skills"
    target_root.mkdir(parents=True, exist_ok=True)
    for root in bundled_roots:
        if not root.exists():
            continue
        for skill_dir in root.iterdir():
            if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
                continue
            dest = target_root / skill_dir.name
            if dest.exists():
                continue
            shutil.copytree(skill_dir, dest)
