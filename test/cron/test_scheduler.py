import asyncio

from cron.scheduler import CronScheduler


def test_cron_scheduler_runs_job():
    scheduler = CronScheduler()
    ran = {"count": 0}

    async def _job():
        ran["count"] += 1

    job_id = scheduler.every(0.01, _job)

    async def _run():
        for _ in range(5):
            await scheduler.run_pending()
            await asyncio.sleep(0.02)

    asyncio.run(_run())
    assert ran["count"] >= 1
    scheduler.disable(job_id)
