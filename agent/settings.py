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
    trim_tools: bool = True
    tool_max: int = 40


@dataclass
class CompressionSettings:
    keep_recent_turns: int = 10


@dataclass
class LLMSettings:
    provider: str = "deepseek"
    model: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com"
    api_key: str | None = None
    tool_choice: str = "auto"


@dataclass
class GatewaySettings:
    host: str = "0.0.0.0"
    port: int = 8787


@dataclass
class MCPSamplingSettings:
    enabled: bool = True
    max_tool_rounds: int = 3


@dataclass
class MCPSettings:
    servers: dict[str, dict] = field(default_factory=dict)
    sampling: MCPSamplingSettings = field(default_factory=MCPSamplingSettings)


@dataclass
class VectorSettings:
    backend: str = "sqlite-vec"
    embedding: str = "hash"


@dataclass
class CronSettings:
    jobs: list[dict] = field(default_factory=list)


@dataclass
class Settings:
    orchestrator_max_iterations: int = 30
    subagent_max_iterations: int = 90
    routing: RoutingSettings = field(default_factory=RoutingSettings)
    compression: CompressionSettings = field(default_factory=CompressionSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)
    gateway: GatewaySettings = field(default_factory=GatewaySettings)
    mcp: MCPSettings = field(default_factory=MCPSettings)
    vector: VectorSettings = field(default_factory=VectorSettings)
    cron: CronSettings = field(default_factory=CronSettings)


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
    settings.routing.trim_tools = bool(routing.get("trim_tools", True))
    settings.routing.tool_max = int(routing.get("tool_max", 40))

    llm = raw.get("llm", {})
    provider = str(llm.get("provider", settings.llm.provider))
    preset_model = settings.llm.model
    preset_base = settings.llm.base_url
    if provider == "openai":
        preset_model = "gpt-4o-mini"
        preset_base = "https://api.openai.com/v1"
    elif provider == "deepseek":
        preset_model = "deepseek-chat"
        preset_base = "https://api.deepseek.com"

    settings.llm = LLMSettings(
        provider=provider,
        model=str(llm.get("model", preset_model)),
        base_url=str(llm.get("base_url", preset_base)),
        api_key=llm.get("api_key"),
        tool_choice=str(llm.get("tool_choice", settings.llm.tool_choice)),
    )

    gateway = raw.get("gateway", {})
    settings.gateway = GatewaySettings(
        host=str(gateway.get("host", settings.gateway.host)),
        port=int(gateway.get("port", settings.gateway.port)),
    )

    mcp = raw.get("mcp_servers", {})
    if isinstance(mcp, dict):
        settings.mcp.servers = {str(k): dict(v or {}) for k, v in mcp.items()}

    mcp_root = raw.get("mcp", {})
    if isinstance(mcp_root, dict):
        sampling = mcp_root.get("sampling", {})
        if isinstance(sampling, dict):
            settings.mcp.sampling = MCPSamplingSettings(
                enabled=bool(sampling.get("enabled", settings.mcp.sampling.enabled)),
                max_tool_rounds=int(
                    sampling.get("max_tool_rounds", settings.mcp.sampling.max_tool_rounds)
                ),
            )

    vector = raw.get("vector", {})
    if isinstance(vector, dict):
        settings.vector = VectorSettings(
            backend=str(vector.get("backend", settings.vector.backend)),
            embedding=str(vector.get("embedding", settings.vector.embedding)),
        )

    cron = raw.get("cron", {})
    if isinstance(cron, dict):
        jobs = cron.get("jobs") or []
        settings.cron = CronSettings(jobs=list(jobs) if isinstance(jobs, list) else [])

    return settings
