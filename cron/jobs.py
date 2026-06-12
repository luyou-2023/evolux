"""Load and run cron jobs from config."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent.settings import Settings, load_settings
from cron.scheduler import CronScheduler
from evolux_constants import get_evolux_home
from gateway.session import SessionSource, build_session_key
from run_agent import EvoluxAgent

logger = logging.getLogger("evolux.cron")


@dataclass
class CronJobConfig:
    job_id: str
    interval_seconds: float
    assistant_id: str
    prompt: str
    enabled: bool = True


def load_cron_jobs(home: Path | None = None, settings: Settings | None = None) -> list[CronJobConfig]:
    cfg = settings or load_settings(home or get_evolux_home())
    jobs: list[CronJobConfig] = []
    for raw in cfg.cron.jobs:
        if not isinstance(raw, dict):
            continue
        job_id = str(raw.get("id") or raw.get("name") or "")
        if not job_id:
            continue
        jobs.append(
            CronJobConfig(
                job_id=job_id,
                interval_seconds=float(raw.get("interval_seconds", 3600)),
                assistant_id=str(raw.get("assistant_id", "default")),
                prompt=str(raw.get("prompt", "")),
                enabled=bool(raw.get("enabled", True)),
            )
        )
    return jobs


def register_cron_jobs(
    scheduler: CronScheduler,
    *,
    home: Path,
    llm_call: Callable[[list[dict[str, Any]]], Any],
    jobs: list[CronJobConfig] | None = None,
) -> list[str]:
    """Register config jobs; returns scheduler job ids."""
    configs = jobs if jobs is not None else load_cron_jobs(home=home)
    registered: list[str] = []
    agents: dict[str, EvoluxAgent] = {}

    def _run_job(job: CronJobConfig) -> None:
        if not job.prompt:
            return
        if job.assistant_id not in agents:
            agents[job.assistant_id] = EvoluxAgent(
                llm_call=llm_call,
                home=home,
                assistant_id=job.assistant_id,
            )
        agent = agents[job.assistant_id]
        session_key = build_session_key(
            job.assistant_id,
            SessionSource(platform="cron", chat_type="job", chat_id=job.job_id),
        )
        result = agent.run_orchestrator_turn(session_key, job.prompt, platform="cron")
        logger.info(
            "cron job %s finished exhausted=%s content_len=%s",
            job.job_id,
            result.exhausted,
            len(result.content or ""),
        )

    for job in configs:
        if not job.enabled:
            continue

        def _make_callback(j: CronJobConfig):
            def _callback() -> None:
                _run_job(j)

            return _callback

        scheduler_id = scheduler.every(job.interval_seconds, _make_callback(job))
        registered.append(scheduler_id)
        logger.info("registered cron job %s every %ss", job.job_id, job.interval_seconds)

    return registered
