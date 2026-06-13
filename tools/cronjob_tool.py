"""Hermes-aligned cronjob tool (action-style job management)."""

from __future__ import annotations

import json

from cron.schedule import parse_schedule
from cron.store import CronJobStore
from evolux_constants import get_evolux_home
from tools.registry import registry, tool_error


def cronjob_tool(
    *,
    action: str,
    job_id: str | None = None,
    name: str | None = None,
    prompt: str | None = None,
    schedule: str | None = None,
    skills: list[str] | None = None,
    deliver: str | None = None,
    assistant_id: str = "default",
    origin_session_key: str = "",
    enabled: bool | None = None,
) -> str:
    store = CronJobStore(home=get_evolux_home())
    action = (action or "").strip().lower()

    if action == "list":
        jobs = store.list_jobs()
        return json.dumps(
            {
                "success": True,
                "jobs": [
                    {
                        "id": job.id,
                        "name": job.name,
                        "state": job.state,
                        "schedule": job.schedule.get("display"),
                        "next_run_at": job.next_run_at,
                        "last_run_at": job.last_run_at,
                        "last_status": job.last_status,
                        "skills": job.skills,
                        "deliver": job.deliver,
                    }
                    for job in jobs
                ],
                "count": len(jobs),
            },
            ensure_ascii=False,
        )

    if action == "create":
        if not schedule or not prompt:
            return tool_error("schedule and prompt are required for create")
        try:
            parse_schedule(schedule)
        except ValueError as exc:
            return tool_error(str(exc))
        job = store.create(
            schedule=schedule,
            prompt=prompt,
            name=name or "",
            skills=list(skills or []),
            deliver=deliver or "local",
            assistant_id=assistant_id,
            origin_session_key=origin_session_key,
        )
        return json.dumps({"success": True, "created": job.id, "name": job.name}, ensure_ascii=False)

    if not job_id:
        return tool_error("job_id is required")

    job = store.get(job_id)
    if job is None and action != "create":
        return tool_error(f"unknown job: {job_id}")

    if action == "remove":
        store.remove(job.id)
        return json.dumps({"success": True, "removed": job.id}, ensure_ascii=False)

    if action == "pause":
        job.state = "paused"
        job.enabled = False
        store.save(job)
        return json.dumps({"success": True, "paused": job.id}, ensure_ascii=False)

    if action == "resume":
        job.state = "scheduled"
        job.enabled = True
        job.ensure_next_run()
        store.save(job)
        return json.dumps({"success": True, "resumed": job.id, "next_run_at": job.next_run_at}, ensure_ascii=False)

    if action == "run":
        job.ensure_next_run()
        from cron.schedule import format_iso
        from datetime import datetime, timezone

        job.next_run_at = format_iso(datetime.now(timezone.utc))
        store.save(job)
        return json.dumps(
            {"success": True, "queued": job.id, "next_run_at": job.next_run_at},
            ensure_ascii=False,
        )

    if action == "update":
        if schedule:
            try:
                spec = parse_schedule(schedule)
            except ValueError as exc:
                return tool_error(str(exc))
            job.schedule = {
                "kind": spec.kind,
                "expr": spec.expr,
                "display": spec.display,
                "interval_seconds": spec.interval_seconds,
            }
            job.ensure_next_run()
        if prompt:
            job.prompt = prompt.strip()
        if name:
            job.name = name.strip()
        if skills is not None:
            job.skills = list(skills)
        if deliver:
            job.deliver = deliver
        if enabled is not None:
            job.enabled = enabled
            job.state = "scheduled" if enabled else "paused"
        store.save(job)
        return json.dumps({"success": True, "updated": job.id}, ensure_ascii=False)

    return tool_error(f"unknown action: {action}")


CRONJOB_SCHEMA = {
    "name": "cronjob",
    "description": (
        "Manage scheduled cron jobs (Hermes-compatible): create, list, update, pause, resume, run, remove."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "update", "pause", "resume", "run", "remove"],
            },
            "job_id": {"type": "string"},
            "name": {"type": "string"},
            "prompt": {"type": "string"},
            "schedule": {"type": "string"},
            "skills": {"type": "array", "items": {"type": "string"}},
            "deliver": {"type": "string"},
            "assistant_id": {"type": "string"},
            "enabled": {"type": "boolean"},
        },
        "required": ["action"],
    },
}


registry.register(
    "cronjob",
    lambda args, **kw: cronjob_tool(
        action=args.get("action", "list"),
        job_id=args.get("job_id"),
        name=args.get("name"),
        prompt=args.get("prompt"),
        schedule=args.get("schedule"),
        skills=args.get("skills"),
        deliver=args.get("deliver"),
        assistant_id=kw.get("assistant_id", "default"),
        origin_session_key=kw.get("origin_session_key", ""),
        enabled=args.get("enabled"),
    ),
    CRONJOB_SCHEMA,
    toolset="cronjob",
)
