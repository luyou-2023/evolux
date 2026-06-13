"""Cron CLI commands (Hermes-compatible)."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from agent.runtime import bootstrap, create_llm_call
from cron.jobs import build_run_context, load_cron_jobs, run_cron_job
from cron.scheduler import CronScheduler, register_cron_scheduler
from cron.store import CronJobStore
from evolux_logging import setup_logging

logger = logging.getLogger("evolux.cron")


def add_cron_parser(sub: argparse._SubParsersAction) -> None:
    cron = sub.add_parser("cron", help="Scheduled agent jobs (Hermes-compatible)")
    cron_sub = cron.add_subparsers(dest="cron_command")

    cron_sub.add_parser("list", help="List scheduled jobs")
    cron_sub.add_parser("status", help="Show scheduler status")

    create = cron_sub.add_parser("create", help="Create a scheduled job")
    create.add_argument("schedule", help='Schedule e.g. "every 2h", "0 9 * * *", "30m"')
    create.add_argument("prompt", help="Prompt to run on schedule")
    create.add_argument("--name", default="", help="Job name")
    create.add_argument("--skill", action="append", default=[], help="Attached skill (repeatable)")
    create.add_argument("--assistant", default="default", help="Assistant id")
    create.add_argument("--deliver", default="local", help="Delivery target: local|origin|feishu")

    add = cron_sub.add_parser("add", help="Alias for create")
    add.add_argument("schedule")
    add.add_argument("prompt")
    add.add_argument("--name", default="")
    add.add_argument("--skill", action="append", default=[])
    add.add_argument("--assistant", default="default")
    add.add_argument("--deliver", default="local")

    pause = cron_sub.add_parser("pause", help="Pause a job")
    pause.add_argument("job_id")
    resume = cron_sub.add_parser("resume", help="Resume a job")
    resume.add_argument("job_id")
    run = cron_sub.add_parser("run", help="Run a job immediately")
    run.add_argument("job_id")
    remove = cron_sub.add_parser("remove", help="Remove a job")
    remove.add_argument("job_id")

    edit = cron_sub.add_parser("edit", help="Edit a job")
    edit.add_argument("job_id")
    edit.add_argument("--schedule")
    edit.add_argument("--prompt")
    edit.add_argument("--name")
    edit.add_argument("--skill", action="append", default=[])
    edit.add_argument("--deliver")

    cron_sub.add_parser("tick", help="Run one scheduler tick")
    start = cron_sub.add_parser("start", help="Run cron scheduler loop")
    start.add_argument("--check", action="store_true", help="Validate config and exit")


def _print_jobs(jobs) -> None:
    if not jobs:
        print("No cron jobs configured. Use: evolux cron create \"every 2h\" \"your prompt\"")
        return
    for job in jobs:
        print(
            f"{job.id}\t{job.state}\t{job.schedule.get('display')}\t"
            f"next={job.next_run_at or '-'}\tassistant={job.assistant_id}\t"
            f"{job.prompt[:48]}"
        )


def _create_job(base: Path, args: argparse.Namespace) -> int:
    store = CronJobStore(home=base)
    job = store.create(
        schedule=args.schedule,
        prompt=args.prompt,
        name=getattr(args, "name", "") or "",
        skills=list(getattr(args, "skill", []) or []),
        assistant_id=getattr(args, "assistant", "default") or "default",
        deliver=getattr(args, "deliver", "local") or "local",
    )
    print(f"Created cron job {job.id} ({job.name}) next={job.next_run_at}")
    return 0


def run_cron(args: argparse.Namespace, home: Path | None = None) -> int:
    base, settings = bootstrap(home)
    setup_logging(base)
    store = CronJobStore(home=base)
    store.migrate_config_jobs(list(settings.cron.jobs or []))
    jobs = load_cron_jobs(base, settings)

    if args.cron_command in {"list", "status"}:
        if args.cron_command == "status":
            pending = [job for job in jobs if job.state == "scheduled"]
            print(f"Cron jobs: {len(jobs)} total, {len(pending)} scheduled")
        _print_jobs(jobs)
        return 0

    if args.cron_command in {"create", "add"}:
        return _create_job(base, args)

    if args.cron_command == "pause":
        job = store.get(args.job_id)
        if job is None:
            print(f"Unknown job: {args.job_id}")
            return 1
        job.state = "paused"
        job.enabled = False
        store.save(job)
        print(f"Paused {job.id}")
        return 0

    if args.cron_command == "resume":
        job = store.get(args.job_id)
        if job is None:
            print(f"Unknown job: {args.job_id}")
            return 1
        job.state = "scheduled"
        job.enabled = True
        job.ensure_next_run()
        store.save(job)
        print(f"Resumed {job.id} next={job.next_run_at}")
        return 0

    if args.cron_command == "remove":
        if store.remove(args.job_id):
            print(f"Removed {args.job_id}")
            return 0
        print(f"Unknown job: {args.job_id}")
        return 1

    if args.cron_command == "run":
        job = store.get(args.job_id)
        if job is None:
            print(f"Unknown job: {args.job_id}")
            return 1
        llm_call = create_llm_call(base, settings)
        ctx = build_run_context(base, llm_call, settings=settings)
        content = run_cron_job(job, ctx=ctx)
        print(f"Ran {job.id} ({len(content)} chars)")
        return 0

    if args.cron_command == "edit":
        job = store.get(args.job_id)
        if job is None:
            print(f"Unknown job: {args.job_id}")
            return 1
        if getattr(args, "schedule", None):
            from cron.schedule import parse_schedule

            spec = parse_schedule(args.schedule)
            job.schedule = {
                "kind": spec.kind,
                "expr": spec.expr,
                "display": spec.display,
                "interval_seconds": spec.interval_seconds,
            }
            job.ensure_next_run()
        if getattr(args, "prompt", None):
            job.prompt = args.prompt
        if getattr(args, "name", None):
            job.name = args.name
        if getattr(args, "skill", None):
            job.skills = list(args.skill)
        if getattr(args, "deliver", None):
            job.deliver = args.deliver
        store.save(job)
        print(f"Updated {job.id}")
        return 0

    if args.cron_command == "tick":
        llm_call = create_llm_call(base, settings)
        scheduler = CronScheduler(home=base)
        ctx = register_cron_scheduler(scheduler, home=base, llm_call=llm_call, settings=settings)
        ran = scheduler.tick(ctx)
        print(f"Tick complete: {ran} job(s) executed")
        return 0

    if args.cron_command == "start":
        if not jobs:
            print("No cron jobs configured.")
            return 1
        if getattr(args, "check", False):
            print(f"{len(jobs)} cron job(s) ready.")
            return 0
        llm_call = create_llm_call(base, settings)
        scheduler = CronScheduler(home=base)
        register_cron_scheduler(scheduler, home=base, llm_call=llm_call, settings=settings)
        print(f"Cron scheduler running (tick={settings.cron.tick_seconds}s). Ctrl+C to stop.")

        async def _main() -> None:
            await scheduler.run_forever(poll_seconds=1.0)

        try:
            asyncio.run(_main())
        except KeyboardInterrupt:
            logger.info("cron stopped")
        return 0

    return 1
