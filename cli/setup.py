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

assistants:
  default:
    name: 默认助手
    platforms:
      cli: {}
"""


def run_setup(home: Path | None = None) -> int:
    base = home or get_evolux_home()
    base.mkdir(parents=True, exist_ok=True)
    for sub in ("skills", "memories", "agents", "vector", "logs"):
        (base / sub).mkdir(parents=True, exist_ok=True)

    config_path = base / "config.yaml"
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        print(f"Created {config_path}")
    else:
        print(f"Config already exists: {config_path}")
    print(f"EVOLUX_HOME={base}")
    return 0
