"""Daily ingestion scheduler — runs at 10:00 AM IST by default."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Any
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config.settings import Settings, get_settings
from ingestion.run import run_ingestion
from scheduler.status import read_status, write_run_result

logger = logging.getLogger(__name__)


def clear_runtime_caches() -> None:
    """Refresh in-memory caches so the API serves the new index."""
    from app.corpus_urls import clear_corpus_url_cache
    from app.retriever import clear_retriever_cache
    from app.scheme_index import clear_scheme_cache

    clear_retriever_cache()
    clear_scheme_cache()
    clear_corpus_url_cache()
    get_settings.cache_clear()


def run_scheduled_ingestion(settings: Settings | None = None) -> dict[str, Any]:
    """
    Run full ingestion with one retry on failure.

    Uses atomic index swap in ingestion.index — live API keeps previous index until success.
    """
    settings = settings or get_settings()
    max_attempts = max(1, settings.scheduler_max_retries)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        logger.info("Scheduled ingestion attempt %s/%s", attempt, max_attempts)
        try:
            summary = run_ingestion()
            clear_runtime_caches()
            write_run_result(success=True, summary=summary, attempt=attempt, settings=settings)
            logger.info("Scheduled ingestion succeeded on attempt %s", attempt)
            return summary
        except Exception as exc:
            last_error = exc
            logger.exception("Scheduled ingestion failed (attempt %s): %s", attempt, exc)
            write_run_result(success=False, error=str(exc), attempt=attempt, settings=settings)
            if attempt < max_attempts:
                delay = settings.scheduler_retry_delay_seconds
                logger.info("Retrying in %s seconds…", delay)
                time.sleep(delay)

    raise RuntimeError("Scheduled ingestion failed after retries") from last_error


def _cron_trigger(settings: Settings) -> CronTrigger:
    tz = ZoneInfo(settings.scheduler_timezone)
    return CronTrigger(
        hour=settings.scheduler_hour,
        minute=settings.scheduler_minute,
        timezone=tz,
    )


def create_scheduler(*, blocking: bool = False) -> BackgroundScheduler | BlockingScheduler:
    settings = get_settings()
    scheduler_cls = BlockingScheduler if blocking else BackgroundScheduler
    tz = ZoneInfo(settings.scheduler_timezone)
    scheduler = scheduler_cls(timezone=tz)
    scheduler.add_job(
        run_scheduled_ingestion,
        _cron_trigger(settings),
        id="daily_ingestion",
        name="Daily Groww corpus ingestion",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    return scheduler


def start_background_scheduler() -> BackgroundScheduler:
    """Start APScheduler in background (for FastAPI lifespan)."""
    settings = get_settings()
    scheduler = create_scheduler(blocking=False)
    scheduler.start()
    logger.info(
        "Scheduler started — daily ingestion at %02d:%02d %s",
        settings.scheduler_hour,
        settings.scheduler_minute,
        settings.scheduler_timezone,
    )
    return scheduler


def run_daemon() -> None:
    """Block until interrupted; fires on cron schedule."""
    settings = get_settings()
    scheduler = create_scheduler(blocking=True)
    logger.info(
        "Scheduler daemon running — daily at %02d:%02d %s (Ctrl+C to stop)",
        settings.scheduler_hour,
        settings.scheduler_minute,
        settings.scheduler_timezone,
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Daily ingestion scheduler")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run ingestion immediately (one-shot)",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run blocking scheduler daemon (default if no flags)",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print last scheduler run status and exit",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.status:
        import json

        print(json.dumps(read_status(), indent=2))
        return

    if args.run_now:
        try:
            summary = run_scheduled_ingestion()
            chunk_count = summary.get("steps", {}).get("chunk", {}).get("chunk_count", 0)
            print(f"Ingestion OK — chunks: {chunk_count}")
        except RuntimeError as exc:
            logger.error("%s", exc)
            sys.exit(1)
        return

    run_daemon()


if __name__ == "__main__":
    main()
