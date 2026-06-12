"""Lightweight interval/cron job scheduler."""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Awaitable, Callable


@dataclass
class ScheduledJob:
    job_id: str
    interval_seconds: float
    callback: Callable[[], Awaitable[None] | None]
    next_run: float = field(default_factory=time.time)
    enabled: bool = True


class CronScheduler:
    """Run periodic jobs in the asyncio loop."""

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}

    def every(self, interval_seconds: float, callback: Callable[[], Awaitable[None] | None]) -> str:
        job_id = str(uuid.uuid4())
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
