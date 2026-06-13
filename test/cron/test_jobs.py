import asyncio

from agent.llm import MockLLMClient, llm_call_adapter
from cron.jobs import load_cron_jobs
from cron.scheduler import CronScheduler, register_cron_scheduler


def test_load_cron_jobs(evolux_home):
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


def test_register_cron_scheduler_ticks(evolux_home):
    (evolux_home / "config.yaml").write_text(
        """
cron:
  tick_seconds: 0.01
  jobs:
    - id: tick
      interval_seconds: 3600
      assistant_id: default
      prompt: "cron hello"
""".strip(),
        encoding="utf-8",
    )
    scheduler = CronScheduler(home=evolux_home)
    llm = MockLLMClient(default_content="cron ok")
    register_cron_scheduler(
        scheduler,
        home=evolux_home,
        llm_call=llm_call_adapter(llm),
    )

    async def _run():
        for _ in range(3):
            await scheduler.run_pending()
            await asyncio.sleep(0.02)

    asyncio.run(_run())
