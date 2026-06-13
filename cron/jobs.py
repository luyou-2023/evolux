"""Execute cron jobs and deliver results (Hermes-aligned)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from agent.settings import Settings, load_settings
from cron.store import CronJob, CronJobStore
from evolux_constants import get_evolux_home
from gateway.session import SessionSource, build_session_key
from run_agent import EvoluxAgent

logger = logging.getLogger("evolux.cron")


@dataclass
class CronRunContext:
    home: Path
    llm_call: Callable[[list[dict[str, Any]]], Any]
    settings: Settings | None = None
    agents: dict[str, EvoluxAgent] | None = None

    def agent_for(self, assistant_id: str) -> EvoluxAgent:
        agents = self.agents if self.agents is not None else {}
        if assistant_id not in agents:
            agents[assistant_id] = EvoluxAgent(
                llm_call=self.llm_call,
                home=self.home,
                assistant_id=assistant_id,
                settings=self.settings or load_settings(self.home),
            )
        if self.agents is None:
            self.agents = agents
        return agents[assistant_id]


def load_cron_jobs(home: Path | None = None, settings: Settings | None = None) -> list[CronJob]:
    base = home or get_evolux_home()
    store = CronJobStore(home=base)
    cfg = settings or load_settings(base)
    store.migrate_config_jobs(list(cfg.cron.jobs or []))
    return store.list_jobs()


def _output_dir(home: Path) -> Path:
    path = home / "cron" / "output"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _wrap_response(job: CronJob, content: str, *, wrap: bool) -> str:
    if not wrap:
        return content
    header = f"[Cron: {job.name}]\n"
    footer = "\n\n— Scheduled task (not part of live conversation history)"
    return f"{header}{content.strip()}{footer}"


def deliver_job_result(
    job: CronJob,
    content: str,
    *,
    home: Path,
    wrap_response: bool = True,
) -> None:
    if not content or content.lstrip().startswith("[SILENT]"):
        return
    text = _wrap_response(job, content, wrap=wrap_response)
    target = (job.deliver or "local").strip().lower()
    if target in {"local", ""}:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = _output_dir(home) / f"{job.id}-{stamp}.md"
        path.write_text(text, encoding="utf-8")
        return
    if target == "origin" and job.origin_session_key:
        logger.info("cron deliver=origin for job=%s session=%s", job.id, job.origin_session_key)
        path = _output_dir(home) / f"{job.id}-origin-latest.md"
        path.write_text(text, encoding="utf-8")
        return
    if target.startswith("feishu:") or target == "feishu":
        logger.info("cron deliver feishu pending integration job=%s", job.id)
        path = _output_dir(home) / f"{job.id}-feishu-latest.md"
        path.write_text(text, encoding="utf-8")
        return
    path = _output_dir(home) / f"{job.id}-deliver-latest.md"
    path.write_text(text, encoding="utf-8")


def run_cron_job(job: CronJob, *, ctx: CronRunContext) -> str:
    if not job.prompt:
        return ""
    agent = ctx.agent_for(job.assistant_id)
    session_key = build_session_key(
        job.assistant_id,
        SessionSource(platform="cron", chat_type="job", chat_id=job.id),
    )
    prompt = job.prompt
    if job.skills:
        skill_block = agent.skill_router.load_for_execution(job.skills)
        if skill_block:
            prompt = f"{skill_block}\n\nTask:\n{job.prompt}"
    result = agent.run_orchestrator_turn(session_key, prompt, platform="cron")
    content = str(result.content or "")
    deliver_job_result(
        job,
        content,
        home=ctx.home,
        wrap_response=bool((ctx.settings or load_settings(ctx.home)).cron.wrap_response),
    )
    logger.info(
        "cron job %s finished exhausted=%s content_len=%s",
        job.id,
        result.exhausted,
        len(content),
    )
    return content


def build_run_context(home: Path, llm_call, settings: Settings | None = None) -> CronRunContext:
    return CronRunContext(
        home=home,
        llm_call=llm_call,
        settings=settings or load_settings(home),
        agents={},
    )
