"""Detect Hermes Agent installs and profiles on the local machine."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

HERMES_HOME_ENV = "HERMES_HOME"
DEFAULT_HERMES_HOME = Path.home() / ".hermes"


@dataclass
class HermesInstallInfo:
    path: Path
    label: str
    kind: str  # default | profile | env
    has_config: bool = False
    has_env: bool = False
    has_state: bool = False
    has_memories: bool = False
    has_skills: bool = False
    has_cron: bool = False
    skill_count: int = 0
    cron_job_count: int = 0
    hermes_cli: bool = False

    @property
    def sediment_summary(self) -> str:
        parts: list[str] = []
        if self.has_memories:
            parts.append("memories")
        if self.has_skills:
            parts.append(f"skills({self.skill_count})")
        if self.has_cron:
            parts.append(f"cron({self.cron_job_count})")
        if self.has_state:
            parts.append("sessions")
        if self.has_config:
            parts.append("config")
        if self.has_env:
            parts.append("secrets")
        return ", ".join(parts) or "empty"


@dataclass
class HermesDetectReport:
    installs: list[HermesInstallInfo] = field(default_factory=list)
    hermes_on_path: bool = False
    hermes_path: str = ""

    @property
    def found(self) -> bool:
        return bool(self.installs)


def get_default_hermes_home() -> Path:
    override = os.environ.get(HERMES_HOME_ENV)
    if override:
        return Path(override).expanduser()
    return DEFAULT_HERMES_HOME


def looks_like_hermes(home: Path) -> bool:
    if not home.is_dir():
        return False
    markers = (
        home / "config.yaml",
        home / "state.db",
        home / "memories" / "MEMORY.md",
        home / "memories" / "USER.md",
        home / "cron" / "jobs.json",
        home / "skills",
    )
    return any(marker.exists() for marker in markers)


def _describe_install(path: Path, *, label: str, kind: str) -> HermesInstallInfo:
    skills_dir = path / "skills"
    skill_count = 0
    if skills_dir.is_dir():
        skill_count = sum(1 for item in skills_dir.iterdir() if (item / "SKILL.md").exists())

    cron_count = 0
    jobs_path = path / "cron" / "jobs.json"
    if jobs_path.exists():
        try:
            import json

            payload = json.loads(jobs_path.read_text(encoding="utf-8"))
            if isinstance(payload, list):
                cron_count = len(payload)
        except (OSError, ValueError):
            cron_count = 0

    return HermesInstallInfo(
        path=path.resolve(),
        label=label,
        kind=kind,
        has_config=(path / "config.yaml").exists(),
        has_env=(path / ".env").exists(),
        has_state=(path / "state.db").exists(),
        has_memories=any((path / "memories" / name).exists() for name in ("MEMORY.md", "USER.md")),
        has_skills=skill_count > 0,
        has_cron=cron_count > 0 or jobs_path.exists(),
        skill_count=skill_count,
        cron_job_count=cron_count,
        hermes_cli=shutil.which("hermes") is not None,
    )


def discover_hermes_installs() -> HermesDetectReport:
    report = HermesDetectReport()
    report.hermes_on_path = shutil.which("hermes") is not None
    if report.hermes_on_path:
        report.hermes_path = shutil.which("hermes") or ""

    seen: set[Path] = set()
    candidates: list[tuple[Path, str, str]] = []

    env_home = os.environ.get(HERMES_HOME_ENV)
    if env_home:
        candidates.append((Path(env_home).expanduser(), "env", "env"))

    default_home = DEFAULT_HERMES_HOME
    candidates.append((default_home, "default", "default"))

    for root, label, kind in candidates:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        if looks_like_hermes(root):
            report.installs.append(_describe_install(root, label=label, kind=kind))

        profiles_root = root / "profiles"
        if not profiles_root.is_dir():
            continue
        for profile_dir in sorted(profiles_root.iterdir()):
            if not profile_dir.is_dir():
                continue
            resolved = profile_dir.resolve()
            if resolved in seen:
                continue
            if not looks_like_hermes(resolved):
                continue
            seen.add(resolved)
            report.installs.append(
                _describe_install(resolved, label=profile_dir.name, kind="profile")
            )

    return report


def format_detect_report(report: HermesDetectReport) -> str:
    lines = ["Hermes detection:"]
    if report.hermes_on_path:
        lines.append(f"  CLI: hermes ({report.hermes_path})")
    else:
        lines.append("  CLI: not on PATH")

    if not report.installs:
        lines.append("  Data: no Hermes home detected (~/.hermes or $HERMES_HOME)")
        return "\n".join(lines)

    lines.append(f"  Data: {len(report.installs)} install(s) found")
    for item in report.installs:
        lines.append(
            f"    • [{item.kind}:{item.label}] {item.path} — {item.sediment_summary}"
        )
    return "\n".join(lines)


def pick_default_source(report: HermesDetectReport) -> Path | None:
    if not report.installs:
        return None
    for item in report.installs:
        if item.kind == "env":
            return item.path
    for item in report.installs:
        if item.kind == "default":
            return item.path
    return report.installs[0].path
