"""Hermes-compatible cron scheduler with tick() and file locking."""

from __future__ import annotations

import asyncio
import fcntl
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from cron.jobs import CronRunContext, build_run_context, run_cron_job
from cron.schedule import format_iso
from cron.store import CronJobStore
from datetime import datetime, timezone
from evolux_constants import get_evolux_home

logger = logging.getLogger("evolux.cron")


@dataclass
class ScheduledJob:
    job_id: str
    interval_seconds: float
    callback: Callable[[], Awaitable[None] | None]
    next_run: float = field(default_factory=time.time)
    enabled: bool = True


class CronScheduler:
    """Run periodic jobs in asyncio loop or via tick()."""

    def __init__(self, home: Path | None = None) -> None:
        self.home = home or get_evolux_home()
        self._jobs: dict[str, ScheduledJob] = {}
        self._lock_path = self.home / "cron" / "scheduler.lock"
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._ctx: CronRunContext | None = None

    def bind_context(self, ctx: CronRunContext) -> None:
        self._ctx = ctx

    def every(self, interval_seconds: float, callback: Callable[[], Awaitable[None] | None]) -> str:
        job_id = f"legacy-{len(self._jobs)+1}"
        self._jobs[job_id] = ScheduledJob(
            job_id=job_id,
            interval_seconds=interval_seconds,
            callback=callback,
            next_run=time.time() + interval_seconds,
        )
        return job_id

    def disable(self, job_id: str) -> None:
        if job_id in self._jobs:
            self._jobs[job_id].enabled = False

    def _acquire_lock(self):
        handle = self._lock_path.open("a+")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return None
        return handle

    def tick(self, ctx: CronRunContext | None = None) -> int:
        run_ctx = ctx or self._ctx
        if run_ctx is None:
            raise RuntimeError("CronScheduler requires a CronRunContext")
        lock = self._acquire_lock()
        if lock is None:
            return 0
        try:
            store = CronJobStore(home=self.home)
            ran = 0
            now = time.time()
            for job in store.list_jobs():
                if job.state != "scheduled" or not job.enabled:
                    continue
                if not job.next_run_at:
                    job.ensure_next_run()
                    store.save(job)
                try:
                    next_dt = datetime.fromisoformat(job.next_run_at.replace("Z", "+00:00"))
                    due = next_dt.timestamp() <= now
                except ValueError:
                    due = False
                if not due:
                    continue
                job.state = "running"
                store.save(job)
                status = "ok"
                try:
                    run_cron_job(job, ctx=run_ctx)
                except Exception:
                    status = "error"
                    logger.exception("cron job %s failed", job.id)
                refreshed = store.get(job.id) or job
                refreshed.last_run_at = format_iso(datetime.now(timezone.utc))
                refreshed.last_status = status
                refreshed.repeat_completed += 1
                spec = refreshed.schedule_spec()
                if spec.kind in {"delay", "at"}:
                    refreshed.state = "completed"
                    refreshed.enabled = False
                    refreshed.next_run_at = None
                else:
                    refreshed.state = "scheduled"
                    refreshed.ensure_next_run()
                store.save(refreshed)
                ran += 1
            return ran
        finally:
            lock.close()

    async def run_pending(self) -> int:
        now = time.time()
        ran = 0
        for job in self._jobs.values():
            if not job.enabled or now < job.next_run:
                continue
            result = job.callback()
            if asyncio.iscoroutine(result):
                await result
            job.next_run = now + job.interval_seconds
            ran += 1
        return ran

    async def run_forever(self, poll_seconds: float = 1.0) -> None:
        while True:
            await self.run_pending()
            await asyncio.sleep(poll_seconds)


def register_cron_scheduler(
    scheduler: CronScheduler,
    *,
    home: Path,
    llm_call,
    settings=None,
) -> CronRunContext:
    ctx = build_run_context(home, llm_call, settings=settings)
    scheduler.bind_context(ctx)
    tick_seconds = float((settings or __import__("agent.settings", fromlist=["load_settings"]).load_settings(home)).cron.tick_seconds)

    def _tick_callback() -> None:
        scheduler.tick(ctx)

    scheduler.every(tick_seconds, _tick_callback)
    return ctx
