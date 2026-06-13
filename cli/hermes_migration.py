"""Migrate Hermes user sediment into Evolux main/sub-agent data layout."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from cli.hermes_detect import looks_like_hermes
from cron.store import CronJobStore
from evolux_constants import get_evolux_home


@dataclass
class MigrationResult:
    source: Path
    target: Path
    preset: str
    dry_run: bool
    copied: list[str] = field(default_factory=list)
    merged: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backup_dir: Path | None = None

    def summary_lines(self) -> list[str]:
        mode = "dry-run" if self.dry_run else "applied"
        lines = [
            f"Hermes → Evolux migration ({mode}, preset={self.preset})",
            f"  source: {self.source}",
            f"  target: {self.target}",
        ]
        if self.backup_dir:
            lines.append(f"  backup: {self.backup_dir}")
        if self.copied:
            lines.append(f"  copied: {', '.join(self.copied)}")
        if self.merged:
            lines.append(f"  merged: {', '.join(self.merged)}")
        if self.skipped:
            lines.append(f"  skipped: {', '.join(self.skipped)}")
        if self.warnings:
            lines.append("  warnings:")
            lines.extend(f"    - {item}" for item in self.warnings)
        return lines


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _merge_env_lines(source: Path, target: Path, *, dry_run: bool) -> bool:
    src = source / ".env"
    if not src.exists():
        return False
    dst = target / ".env"
    existing: dict[str, str] = {}
    if dst.exists():
        for line in dst.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            existing[key.strip()] = value
    merged_lines: list[str] = []
    if dst.exists():
        merged_lines.extend(dst.read_text(encoding="utf-8").splitlines())
        if merged_lines and merged_lines[-1].strip():
            merged_lines.append("")
    merged_lines.append("# --- imported from Hermes ---")
    changed = False
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in existing:
            continue
        merged_lines.append(f"{key}={value}")
        changed = True
    if changed and not dry_run:
        dst.write_text("\n".join(merged_lines).rstrip() + "\n", encoding="utf-8")
    return changed


def _append_memory_file(source: Path, target: Path, name: str, *, overwrite: bool, dry_run: bool) -> bool:
    src = source / "memories" / name
    if not src.exists():
        return False
    dst = target / "memories" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists() or overwrite:
        if not dry_run:
            shutil.copy2(src, dst)
        return True
    existing = dst.read_text(encoding="utf-8")
    incoming = src.read_text(encoding="utf-8")
    marker = f"\n\n<!-- imported from Hermes ({_utc_stamp()}) -->\n"
    if incoming.strip() in existing:
        return False
    if not dry_run:
        dst.write_text(existing.rstrip() + marker + incoming.strip() + "\n", encoding="utf-8")
    return True


def _import_skills(
    source: Path,
    target: Path,
    *,
    overwrite: bool,
    dry_run: bool,
) -> tuple[int, int]:
    src_root = source / "skills"
    if not src_root.is_dir():
        return 0, 0
    imported = 0
    skipped = 0
    for skill_dir in sorted(src_root.iterdir()):
        if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
            continue
        primary = target / "skills" / skill_dir.name
        fallback = target / "skills" / "hermes-imports" / skill_dir.name
        if primary.exists() and not overwrite:
            dest = fallback
            skipped += 1
        else:
            dest = primary
        if dest.exists() and not overwrite:
            skipped += 1
            continue
        if not dry_run:
            if dest.exists():
                shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(skill_dir, dest)
        imported += 1
    return imported, skipped


def _import_cron(source: Path, target: Path, *, dry_run: bool) -> int:
    jobs_path = source / "cron" / "jobs.json"
    store = CronJobStore(home=target)
    if jobs_path.exists():
        if dry_run:
            try:
                payload = json.loads(jobs_path.read_text(encoding="utf-8"))
                return len(payload) if isinstance(payload, list) else 0
            except (OSError, ValueError):
                return 0
        payload = json.loads(jobs_path.read_text(encoding="utf-8"))
        if isinstance(payload, list) and payload:
            existing = {job.id for job in store.list_jobs()}
            imported = 0
            for raw in payload:
                if not isinstance(raw, dict):
                    continue
                job_id = str(raw.get("id") or raw.get("name") or "")
                if job_id and job_id in existing:
                    continue
                from cron.store import CronJob

                job = CronJob.from_dict(raw)
                job.ensure_next_run()
                store.save(job)
                imported += 1
            return imported
    hermes_cfg = _read_yaml(source / "config.yaml")
    legacy = hermes_cfg.get("cron", {}).get("jobs") if isinstance(hermes_cfg.get("cron"), dict) else []
    if dry_run:
        return len(legacy) if isinstance(legacy, list) else 0
    return store.migrate_config_jobs(list(legacy or []))


def _map_hermes_llm(hermes_cfg: dict[str, Any]) -> dict[str, Any]:
    model = str(hermes_cfg.get("model") or "").strip()
    providers = hermes_cfg.get("providers")
    provider_name = ""
    provider_cfg: dict[str, Any] = {}
    if isinstance(providers, dict):
        for name, cfg in providers.items():
            if isinstance(cfg, dict) and cfg.get("enabled", True):
                provider_name = str(name)
                provider_cfg = cfg
                break
        if not provider_name and providers:
            provider_name = next(iter(providers.keys()))
            maybe = providers[provider_name]
            provider_cfg = maybe if isinstance(maybe, dict) else {}

    mapped_model = str(provider_cfg.get("model") or model or "deepseek-chat")
    base_url = str(provider_cfg.get("base_url") or "").strip()

    if provider_name in {"openrouter", "open_router"} or "openrouter.ai" in base_url:
        return {
            "provider": "openai",
            "model": mapped_model,
            "base_url": base_url or "https://openrouter.ai/api/v1",
        }
    if provider_name in {"deepseek"} or "deepseek.com" in base_url:
        return {
            "provider": "deepseek",
            "model": mapped_model or "deepseek-chat",
            "base_url": base_url or "https://api.deepseek.com",
        }
    if provider_name in {"openai"} or "api.openai.com" in base_url:
        return {
            "provider": "openai",
            "model": mapped_model or "gpt-4o-mini",
            "base_url": base_url or "https://api.openai.com/v1",
        }
    if model:
        return {"provider": "openai", "model": model, "base_url": base_url or "https://api.openai.com/v1"}
    return {}


def _upgrade_feishu_assistants_for_coexistence(
    cfg: dict[str, Any],
    *,
    source: Path,
    hermes_gateway_active: bool,
) -> list[str]:
    """Pick websocket, or shared_hermes when Hermes gateway still owns Feishu."""
    changed: list[str] = []
    assistants = cfg.get("assistants")
    if not isinstance(assistants, dict):
        return changed
    target_mode = "shared_hermes" if hermes_gateway_active else "websocket"
    for assistant_id, assistant_cfg in assistants.items():
        if not isinstance(assistant_cfg, dict):
            continue
        platforms = assistant_cfg.get("platforms")
        if not isinstance(platforms, dict):
            continue
        feishu = platforms.get("feishu")
        if not isinstance(feishu, dict):
            continue
        current = str(feishu.get("mode") or "webhook").lower()
        if current != target_mode:
            feishu["mode"] = target_mode
            changed.append(f"{assistant_id}:{target_mode}")
    return changed


def _apply_hermes_gateway_compat_settings(cfg: dict[str, Any], *, source: Path) -> list[str]:
    """Avoid port clashes with Hermes (8787 dashboard, 8765 Feishu webhook)."""
    from gateway.platforms.feishu_hermes import (
        EVOLUX_FALLBACK_GATEWAY_PORT,
        HERMES_DEFAULT_FEISHU_WEBHOOK_PORT,
        read_hermes_gateway_port,
    )

    merged: list[str] = []
    gateway = cfg.setdefault("gateway", {})
    if not isinstance(gateway, dict):
        return merged

    hermes_port = read_hermes_gateway_port(source) or gateway.get("port")
    evolux_port = gateway.get("port")
    try:
        evolux_port_int = int(evolux_port) if evolux_port is not None else None
    except (TypeError, ValueError):
        evolux_port_int = None
    try:
        hermes_port_int = int(hermes_port) if hermes_port is not None else None
    except (TypeError, ValueError):
        hermes_port_int = None

    if evolux_port_int is None or (
        hermes_port_int is not None and evolux_port_int == hermes_port_int
    ):
        gateway["port"] = EVOLUX_FALLBACK_GATEWAY_PORT
        merged.append("gateway.port")

    if gateway.get("feishu_webhook_port") in (None, ""):
        gateway["feishu_webhook_port"] = HERMES_DEFAULT_FEISHU_WEBHOOK_PORT
        merged.append("gateway.feishu_webhook_port")

    if "hermes_compat" not in gateway:
        gateway["hermes_compat"] = True
        merged.append("gateway.hermes_compat")

    return merged


def _merge_config(source: Path, target: Path, *, dry_run: bool) -> list[str]:
    src_cfg = _read_yaml(source / "config.yaml")
    if not src_cfg:
        return []
    dst_path = target / "config.yaml"
    dst_cfg = _read_yaml(dst_path)
    merged_keys: list[str] = []

    llm_patch = _map_hermes_llm(src_cfg)
    if llm_patch:
        dst_cfg.setdefault("llm", {})
        if isinstance(dst_cfg["llm"], dict):
            for key, value in llm_patch.items():
                if key not in dst_cfg["llm"] or not dst_cfg["llm"].get(key):
                    dst_cfg["llm"][key] = value
            merged_keys.append("llm")

    src_mcp = src_cfg.get("mcp_servers")
    if isinstance(src_mcp, dict) and src_mcp:
        dst_mcp = dst_cfg.setdefault("mcp_servers", {})
        if isinstance(dst_mcp, dict):
            for name, cfg in src_mcp.items():
                if name not in dst_mcp:
                    entry = dict(cfg) if isinstance(cfg, dict) else {}
                    entry["enabled"] = False
                    dst_mcp[name] = entry
            merged_keys.append("mcp_servers")
        mcp_root = dst_cfg.setdefault("mcp", {})
        if isinstance(mcp_root, dict) and "discover_on_startup" not in mcp_root:
            mcp_root["discover_on_startup"] = False
            merged_keys.append("mcp.discover_on_startup")

    src_gateway = src_cfg.get("gateway")
    if isinstance(src_gateway, dict) and src_gateway:
        dst_gateway = dst_cfg.setdefault("gateway", {})
        if isinstance(dst_gateway, dict):
            for key in ("host", "port"):
                if key in src_gateway and key not in dst_gateway:
                    dst_gateway[key] = src_gateway[key]
            merged_keys.append("gateway")

    src_compression = src_cfg.get("compression")
    if isinstance(src_compression, dict) and src_compression:
        dst_compression = dst_cfg.setdefault("compression", {})
        if isinstance(dst_compression, dict):
            for key, value in src_compression.items():
                if key not in dst_compression:
                    dst_compression[key] = value
            merged_keys.append("compression")

    src_assistants = src_cfg.get("assistants")
    if isinstance(src_assistants, dict) and src_assistants:
        dst_assistants = dst_cfg.setdefault("assistants", {})
        if isinstance(dst_assistants, dict):
            for assistant_id, cfg in src_assistants.items():
                if assistant_id not in dst_assistants and isinstance(cfg, dict):
                    dst_assistants[assistant_id] = cfg
            merged_keys.append("assistants")

    compat = _apply_hermes_gateway_compat_settings(dst_cfg, source=source)
    if compat:
        merged_keys.extend(compat)

    from gateway.platforms.feishu_hermes import hermes_gateway_running

    upgraded = _upgrade_feishu_assistants_for_coexistence(
        dst_cfg,
        source=source,
        hermes_gateway_active=hermes_gateway_running(source),
    )
    if upgraded:
        merged_keys.append("feishu.coexistence")

    if merged_keys and not dry_run:
        _write_yaml(dst_path, dst_cfg)
    return merged_keys


def _archive_hermes_state(source: Path, backup_dir: Path, *, dry_run: bool) -> bool:
    state = source / "state.db"
    if not state.exists():
        return False
    if not dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(state, backup_dir / "state.db")
    return True


def _ensure_evolux_layout(target: Path) -> None:
    for sub in ("skills", "memories", "agents", "vector", "logs", "state", "cron", "migration"):
        (target / sub).mkdir(parents=True, exist_ok=True)
    registry = target / "agents" / "registry.json"
    if not registry.exists():
        registry.write_text(json.dumps({"agents": []}, indent=2), encoding="utf-8")


def migrate_from_hermes(
    source: Path,
    target: Path | None = None,
    *,
    preset: str = "user-data",
    overwrite: bool = False,
    dry_run: bool = False,
    migrate_secrets: bool | None = None,
) -> MigrationResult:
    src = source.expanduser().resolve()
    dst = (target or get_evolux_home()).expanduser().resolve()
    if not looks_like_hermes(src):
        raise ValueError(f"Not a Hermes home: {src}")

    include_secrets = preset == "full" if migrate_secrets is None else migrate_secrets
    result = MigrationResult(source=src, target=dst, preset=preset, dry_run=dry_run)

    if not dry_run:
        _ensure_evolux_layout(dst)
        backup_dir = dst / "migration" / "hermes" / _utc_stamp()
        backup_dir.mkdir(parents=True, exist_ok=True)
        result.backup_dir = backup_dir
        for rel in ("config.yaml", ".env", "memories/MEMORY.md", "memories/USER.md", "cron/jobs.json"):
            path = src / rel
            if path.exists():
                dest = backup_dir / "hermes-source" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if path.is_dir():
                    shutil.copytree(path, dest)
                else:
                    shutil.copy2(path, dest)
    else:
        backup_dir = dst / "migration" / "hermes" / "dry-run"

    for name in ("MEMORY.md", "USER.md"):
        if _append_memory_file(src, dst, name, overwrite=overwrite, dry_run=dry_run):
            result.copied.append(f"memories/{name}")

    soul = src / "SOUL.md"
    if soul.exists():
        dest = dst / "memories" / "SOUL.md"
        if overwrite or not dest.exists():
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(soul, dest)
            result.copied.append("memories/SOUL.md")
        else:
            result.skipped.append("memories/SOUL.md")

    imported, skipped = _import_skills(src, dst, overwrite=overwrite, dry_run=dry_run)
    if imported:
        result.copied.append(f"skills({imported})")
    if skipped:
        result.skipped.append(f"skills({skipped} conflict)")

    cron_count = _import_cron(src, dst, dry_run=dry_run)
    if cron_count:
        result.merged.append(f"cron({cron_count})")

    merged = _merge_config(src, dst, dry_run=dry_run)
    result.merged.extend(merged)
    if "mcp_servers" in merged:
        result.warnings.append(
            "MCP servers imported with enabled: false — Hermes keeps subprocess MCP; "
            "enable in Evolux config only if you want Evolux to spawn them locally."
        )

    if _archive_hermes_state(src, backup_dir, dry_run=dry_run):
        result.copied.append("state.db (archived)")
        result.warnings.append(
            "Hermes sessions are archived under migration/hermes; Evolux session schema differs — start fresh sessions in Evolux."
        )

    if include_secrets:
        if _merge_env_lines(src, dst, dry_run=dry_run):
            result.merged.append(".env")
    elif (src / ".env").exists():
        result.skipped.append(".env (use --preset full to import secrets)")

    note = dst / "memories" / "HERMES_MIGRATION.md"
    if not dry_run:
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(
            "\n".join(
                [
                    "# Hermes migration",
                    "",
                    f"- source: `{src}`",
                    f"- migrated_at: {_utc_stamp()}",
                    f"- preset: {preset}",
                    "",
                    "Imported sediment is available to the orchestrator via MEMORY/USER and skills.",
                    "Persistent sub-agents live in `agents/registry.json` and are created by Evolux routing/expert promotion.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        result.copied.append("memories/HERMES_MIGRATION.md")

    return result
