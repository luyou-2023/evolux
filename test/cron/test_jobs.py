import asyncio

from agent.llm import MockLLMClient, llm_call_adapter
from cron.jobs import load_cron_jobs, register_cron_jobs
from cron.scheduler import CronScheduler


def test_load_cron_jobs(evolux_home):
    (evolux_home / "config.yaml").write_text(
        """
cron:
  jobs:
    - id: heartbeat
      interval_seconds: 0.01
      assistant_id: default
      prompt: "ping"
      enabled: true
""".strip(),
        encoding="utf-8",
    )
    jobs = load_cron_jobs(evolux_home)
    assert len(jobs) == 1
    assert jobs[0].job_id == "heartbeat"


def test_register_cron_jobs_runs_agent(evolux_home):
    (evolux_home / "config.yaml").write_text(
        """
cron:
  jobs:
    - id: tick
      interval_seconds: 0.01
      assistant_id: default
      prompt: "cron hello"
""".strip(),
        encoding="utf-8",
    )
    scheduler = CronScheduler()
    llm = MockLLMClient(default_content="cron ok")
    register_cron_jobs(
        scheduler,
        home=evolux_home,
        llm_call=llm_call_adapter(llm),
        jobs=load_cron_jobs(evolux_home),
    )

    async def _run():
        for _ in range(5):
            await scheduler.run_pending()
            await asyncio.sleep(0.02)

    asyncio.run(_run())
    assert llm.calls
