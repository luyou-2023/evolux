"""Persistent cron job store (Hermes-compatible jobs.json)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cron.schedule import ScheduleSpec, compute_next_run, format_iso, parse_schedule
from evolux_constants import get_evolux_home


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class CronJob:
    id: str
    name: str
    prompt: str
    schedule: dict[str, Any]
    skills: list[str] = field(default_factory=list)
    deliver: str = "local"
    assistant_id: str = "default"
    state: str = "scheduled"
    enabled: bool = True
    next_run_at: str | None = None
    last_run_at: str | None = None
    last_status: str | None = None
    created_at: str = field(default_factory=_utc_now)
    origin_session_key: str = ""
    repeat_completed: int = 0

    @property
    def job_id(self) -> str:
        return self.id

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> CronJob:
        skills = raw.get("skills")
        if skills is None and raw.get("skill"):
            skills = [str(raw["skill"])]
        payload = dict(raw)
        payload["skills"] = list(skills or [])
        return cls(**{k: payload[k] for k in cls.__dataclass_fields__ if k in payload})

    def schedule_spec(self) -> ScheduleSpec:
        return ScheduleSpec(
            kind=str(self.schedule.get("kind") or "interval"),
            expr=str(self.schedule.get("expr") or ""),
            display=str(self.schedule.get("display") or self.schedule.get("expr") or ""),
            interval_seconds=self.schedule.get("interval_seconds"),
        )

    def ensure_next_run(self) -> None:
        if self.state != "scheduled" or not self.enabled:
            return
        spec = self.schedule_spec()
        if spec.kind == "interval" and spec.interval_seconds is None:
            parsed = parse_schedule(spec.expr)
            spec.interval_seconds = parsed.interval_seconds
        after = datetime.now(timezone.utc)
        if self.next_run_at:
            try:
                after = datetime.fromisoformat(self.next_run_at.replace("Z", "+00:00"))
            except ValueError:
                after = datetime.now(timezone.utc)
        self.next_run_at = format_iso(compute_next_run(spec, after=after))


class CronJobStore:
    def __init__(self, home: Path | None = None):
        self.home = home or get_evolux_home()
        self.dir = self.home / "cron"
        self.path = self.dir / "jobs.json"
        self.dir.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict[str, Any]]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, jobs: list[dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(jobs, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def list_jobs(self) -> list[CronJob]:
        return [CronJob.from_dict(item) for item in self._read()]

    def get(self, job_id: str) -> CronJob | None:
        for item in self.list_jobs():
            if item.id == job_id or item.name == job_id:
                return item
        return None

    def save(self, job: CronJob) -> CronJob:
        raw_jobs = self._read()
        payload = asdict(job)
        replaced = False
        for idx, item in enumerate(raw_jobs):
            if item.get("id") == job.id:
                raw_jobs[idx] = payload
                replaced = True
                break
        if not replaced:
            raw_jobs.append(payload)
        self._write(raw_jobs)
        return job

    def remove(self, job_id: str) -> bool:
        jobs = self.list_jobs()
        new_jobs = [asdict(item) for item in jobs if item.id != job_id and item.name != job_id]
        if len(new_jobs) == len(jobs):
            return False
        self._write(new_jobs)
        return True

    def create(
        self,
        *,
        schedule: str,
        prompt: str,
        name: str = "",
        skills: list[str] | None = None,
        deliver: str = "local",
        assistant_id: str = "default",
        origin_session_key: str = "",
    ) -> CronJob:
        spec = parse_schedule(schedule)
        job = CronJob(
            id=uuid.uuid4().hex[:12],
            name=name or f"job-{uuid.uuid4().hex[:6]}",
            prompt=prompt.strip(),
            schedule={
                "kind": spec.kind,
                "expr": spec.expr,
                "display": spec.display,
                "interval_seconds": spec.interval_seconds,
            },
            skills=list(skills or []),
            deliver=deliver or "local",
            assistant_id=assistant_id,
            origin_session_key=origin_session_key,
            state="scheduled",
            enabled=True,
        )
        job.next_run_at = format_iso(compute_next_run(spec))
        return self.save(job)

    def migrate_config_jobs(self, legacy_jobs: list[dict[str, Any]]) -> int:
        if not legacy_jobs:
            return 0
        existing_ids = {item.id for item in self.list_jobs()}
        migrated = 0
        for raw in legacy_jobs:
            if not isinstance(raw, dict):
                continue
            job_id = str(raw.get("id") or raw.get("name") or "")
            if not job_id or job_id in existing_ids:
                continue
            interval = float(raw.get("interval_seconds", 3600))
            hours = max(1, int(interval // 3600)) if interval >= 3600 else 1
            unit = "h" if interval >= 3600 else "m"
            amount = hours if unit == "h" else max(1, int(interval // 60))
            schedule = f"every {amount}{unit}"
            spec = parse_schedule(schedule)
            enabled = bool(raw.get("enabled", True))
            job = CronJob(
                id=job_id,
                name=job_id,
                prompt=str(raw.get("prompt") or ""),
                schedule={
                    "kind": spec.kind,
                    "expr": spec.expr,
                    "display": spec.display,
                    "interval_seconds": spec.interval_seconds,
                },
                assistant_id=str(raw.get("assistant_id", "default")),
                state="scheduled" if enabled else "paused",
                enabled=enabled,
            )
            job.ensure_next_run()
            self.save(job)
            existing_ids.add(job_id)
            migrated += 1
        return migrated
