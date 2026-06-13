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


def run_setup(home: Path | None = None) -> int:
    base = home or get_evolux_home()
    base.mkdir(parents=True, exist_ok=True)
    for sub in ("skills", "memories", "agents", "vector", "logs", "state"):
        (base / sub).mkdir(parents=True, exist_ok=True)

    _seed_bundled_skills(base)

    config_path = base / "config.yaml"
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"Created {config_path}")
    else:
        print(f"Config already exists: {config_path}")
    print(f"EVOLUX_HOME={base}")
    return 0


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
