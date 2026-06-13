import asyncio
import json

from agent.llm import MockLLMClient, llm_call_adapter
from cron.jobs import build_run_context, load_cron_jobs, run_cron_job
from cron.schedule import compute_next_run, parse_schedule
from cron.scheduler import CronScheduler, register_cron_scheduler
from cron.store import CronJobStore
from tools.cronjob_tool import cronjob_tool


def test_parse_schedule_formats():
    interval = parse_schedule("every 2h")
    assert interval.kind == "interval"
    assert interval.interval_seconds == 7200.0

    delay = parse_schedule("30m")
    assert delay.kind == "delay"

    cron = parse_schedule("0 9 * * *")
    assert cron.kind == "cron"
    nxt = compute_next_run(cron)
    assert nxt.hour == 9
    assert nxt.minute == 0


def test_load_cron_jobs_migrates_config(evolux_home):
    (evolux_home / "config.yaml").write_text(
        """
cron:
  jobs:
    - id: heartbeat
      interval_seconds: 3600
      assistant_id: default
      prompt: "ping"
      enabled: true
""".strip(),
        encoding="utf-8",
    )
    jobs = load_cron_jobs(evolux_home)
    assert len(jobs) == 1
    assert jobs[0].job_id == "heartbeat"
    assert (evolux_home / "cron" / "jobs.json").exists()


def test_cronjob_tool_create_and_list(evolux_home, monkeypatch):
    monkeypatch.setenv("EVOLUX_HOME", str(evolux_home))
    out = json.loads(
        cronjob_tool(
            action="create",
            schedule="every 1h",
            prompt="Summarize inbox",
            name="inbox",
        )
    )
    assert out["success"] is True
    listed = json.loads(cronjob_tool(action="list"))
    assert listed["count"] == 1


def test_scheduler_tick_runs_due_job(evolux_home):
    store = CronJobStore(home=evolux_home)
    job = store.create(schedule="every 1h", prompt="cron hello", name="tick-test")
    from cron.schedule import format_iso
    from datetime import datetime, timezone

    job.next_run_at = format_iso(datetime.now(timezone.utc))
    store.save(job)

    scheduler = CronScheduler(home=evolux_home)
    llm = MockLLMClient(default_content="cron ok")
    ctx = register_cron_scheduler(
        scheduler,
        home=evolux_home,
        llm_call=llm_call_adapter(llm),
    )
    ran = scheduler.tick(ctx)
    assert ran == 1
    assert llm.calls
    refreshed = store.get(job.id)
    assert refreshed is not None
    assert refreshed.last_status == "ok"


def test_run_cron_job_writes_output(evolux_home):
    store = CronJobStore(home=evolux_home)
    job = store.create(schedule="30m", prompt="one shot", name="once")
    llm = MockLLMClient(default_content="done")
    ctx = build_run_context(evolux_home, llm_call_adapter(llm))
    run_cron_job(job, ctx=ctx)
    outputs = list((evolux_home / "cron" / "output").glob("*.md"))
    assert outputs
