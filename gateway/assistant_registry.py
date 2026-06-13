"""Multi-assistant configuration registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent.routing import FusionWeights
from evolux_constants import get_evolux_home


@dataclass
class AssistantConfig:
    assistant_id: str
    name: str
    platforms: dict[str, dict[str, Any]] = field(default_factory=dict)
    skills_allowlist: list[str] = field(default_factory=list)
    routing_fusion: FusionWeights | None = None


class AssistantRegistry:
    """Load assistant definitions from config.yaml."""

    def __init__(self, home: Path | None = None):
        self.home = home or get_evolux_home()
        self._assistants: dict[str, AssistantConfig] = {}
        self.reload()

    def reload(self) -> None:
        self._assistants = {}
        config_path = self.home / "config.yaml"
        if not config_path.exists():
            self._assistants["default"] = AssistantConfig(
                assistant_id="default",
                name="默认助手",
                platforms={"cli": {}},
            )
            return

        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        assistants = raw.get("assistants") or {}
        if not assistants:
            self._assistants["default"] = AssistantConfig(
                assistant_id="default",
                name="默认助手",
                platforms={"cli": {}},
            )
            return

        for assistant_id, cfg in assistants.items():
            if not isinstance(cfg, dict):
                continue
            routing = cfg.get("routing") or {}
            fusion_raw = routing.get("fusion") or {}
            routing_fusion = None
            if fusion_raw:
                routing_fusion = FusionWeights(
                    vector_weight=float(fusion_raw.get("vector_weight", 0.5)),
                    skill_overlap_weight=float(fusion_raw.get("skill_overlap_weight", 0.4)),
                    recency_weight=float(fusion_raw.get("recency_weight", 0.1)),
                )
            self._assistants[assistant_id] = AssistantConfig(
                assistant_id=assistant_id,
                name=str(cfg.get("name", assistant_id)),
                platforms=dict(cfg.get("platforms") or {}),
                skills_allowlist=list(cfg.get("skills_allowlist") or []),
                routing_fusion=routing_fusion,
            )

    def get(self, assistant_id: str) -> AssistantConfig | None:
        return self._assistants.get(assistant_id)

    def list(self) -> list[AssistantConfig]:
        return sorted(self._assistants.values(), key=lambda item: item.assistant_id)

    def resolve_for_platform(self, platform: str, *, preferred: str | None = None) -> AssistantConfig:
        if preferred and preferred in self._assistants:
            assistant = self._assistants[preferred]
            if platform in assistant.platforms:
                return assistant

        for assistant in self.list():
            if platform in assistant.platforms:
                return assistant

        default = self._assistants.get("default")
        if default:
            return default
        raise KeyError(f"no assistant configured for platform: {platform}")

    def resolve_for_feishu_app(self, app_id: str) -> AssistantConfig | None:
        app_id = str(app_id or "").strip()
        if not app_id:
            return None
        matches: list[AssistantConfig] = []
        for assistant in self.list():
            feishu = assistant.platforms.get("feishu") or {}
            if str(feishu.get("app_id") or "") == app_id:
                matches.append(assistant)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return matches[0]
        return None

    def bind_platform(
        self,
        assistant_id: str,
        platform: str,
        platform_config: dict[str, Any],
    ) -> None:
        config_path = self.home / "config.yaml"
        raw: dict[str, Any] = {}
        if config_path.exists():
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

        assistants = raw.setdefault("assistants", {})
        entry = assistants.setdefault(assistant_id, {"name": assistant_id, "platforms": {}})
        entry.setdefault("platforms", {})[platform] = platform_config
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
        self.reload()

    def ensure_assistant(self, assistant_id: str, *, name: str | None = None) -> None:
        """Create assistant entry if missing (CLI platform by default)."""
        config_path = self.home / "config.yaml"
        raw: dict[str, Any] = {}
        if config_path.exists():
            raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

        assistants = raw.setdefault("assistants", {})
        if assistant_id not in assistants:
            assistants[assistant_id] = {
                "name": name or assistant_id,
                "platforms": {"cli": {}},
            }
        elif name:
            entry = assistants[assistant_id]
            if isinstance(entry, dict):
                entry["name"] = name
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
        self.reload()
