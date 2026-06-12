"""Runtime settings loaded from config.yaml with sane defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from agent.routing import FusionWeights
from evolux_constants import get_evolux_home


@dataclass
class RoutingSettings:
    fusion: FusionWeights = field(default_factory=FusionWeights)
    skill_top_k: int = 5
    subagent_top_k: int = 5
    enable_keyword: bool = True
    enable_vector: bool = True


@dataclass
class CompressionSettings:
    keep_recent_turns: int = 10


@dataclass
class Settings:
    orchestrator_max_iterations: int = 30
    subagent_max_iterations: int = 90
    routing: RoutingSettings = field(default_factory=RoutingSettings)
    compression: CompressionSettings = field(default_factory=CompressionSettings)


def load_settings(home: Path | None = None) -> Settings:
    base = home or get_evolux_home()
    settings = Settings()
    config_path = base / "config.yaml"
    if not config_path.exists():
        return settings

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    orch = raw.get("orchestrator", {})
    if "max_iterations" in orch:
        settings.orchestrator_max_iterations = int(orch["max_iterations"])

    sub = raw.get("subagent", {})
    if "max_iterations" in sub:
        settings.subagent_max_iterations = int(sub["max_iterations"])

    compression = raw.get("compression", {})
    if "keep_recent_turns" in compression:
        settings.compression.keep_recent_turns = int(compression["keep_recent_turns"])

    routing = raw.get("routing", {})
    fusion = routing.get("fusion", {})
    settings.routing.fusion = FusionWeights(
        vector_weight=float(fusion.get("vector_weight", 0.5)),
        skill_overlap_weight=float(fusion.get("skill_overlap_weight", 0.4)),
        recency_weight=float(fusion.get("recency_weight", 0.1)),
    )
    skill_identify = routing.get("skill_identify", {})
    settings.routing.skill_top_k = int(skill_identify.get("top_k", 5))
    settings.routing.enable_keyword = bool(skill_identify.get("enable_keyword", True))
    settings.routing.enable_vector = bool(skill_identify.get("enable_vector", True))
    settings.routing.subagent_top_k = int(routing.get("subagent_top_k", 5))

    return settings
