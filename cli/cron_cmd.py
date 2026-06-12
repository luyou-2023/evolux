"""Cron CLI commands."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from agent.runtime import bootstrap, create_llm_call
from cron.jobs import load_cron_jobs, register_cron_jobs
from cron.scheduler import CronScheduler
from evolux_logging import setup_logging

logger = logging.getLogger("evolux.cron")


def add_cron_parser(sub: argparse._SubParsersAction) -> None:
    cron = sub.add_parser("cron", help="Scheduled agent jobs")
    cron_sub = cron.add_subparsers(dest="cron_command")

    cron_sub.add_parser("list", help="List configured cron jobs")

    start = cron_sub.add_parser("start", help="Run cron scheduler loop")
    start.add_argument("--check", action="store_true", help="Validate config and exit")


def run_cron(args: argparse.Namespace, home: Path | None = None) -> int:
    base, settings = bootstrap(home)
    setup_logging(base)
    jobs = load_cron_jobs(base, settings)

    if args.cron_command == "list":
        if not jobs:
            print("No cron jobs configured. Add cron.jobs to ~/.evolux/config.yaml")
            return 0
        for job in jobs:
            status = "enabled" if job.enabled else "disabled"
            print(
                f"{job.job_id}\t{status}\t{job.interval_seconds}s\t"
                f"assistant={job.assistant_id}\t{job.prompt[:40]}"
            )
        return 0

    if args.cron_command == "start":
        if not jobs:
            print("No cron jobs configured.")
            return 1
        if getattr(args, "check", False):
            print(f"{len(jobs)} cron job(s) ready.")
            return 0

        llm_call = create_llm_call(base, settings)
        scheduler = CronScheduler()
        register_cron_jobs(scheduler, home=base, llm_call=llm_call, jobs=jobs)
        print(f"Cron scheduler running with {len(jobs)} job(s). Ctrl+C to stop.")

        async def _main() -> None:
            await scheduler.run_forever(poll_seconds=1.0)

        try:
            asyncio.run(_main())
        except KeyboardInterrupt:
            logger.info("cron stopped")
        return 0

    return 1
