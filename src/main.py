from os import getenv, name
from datetime import datetime
from pathlib import Path
from logging import getLogger

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.jobstores.base import JobLookupError
from dotenv import load_dotenv

from scraper import Scraper
from get_events_from_calendar import get_events
from logger import configure_logger


load_dotenv()

base_path = Path(__file__).parent
configure_logger(base_path)

scheduler = BlockingScheduler()
logger = getLogger(__file__)


def run_event(switch: bool):
    logger.debug("Running scraper")
    with Scraper(getenv("SWITCH_URL", None), getenv("SWITCH_USERNAME", None), getenv("SWITCH_PASSWORD", None)) as sc:
        sc.run(switch)


def cleanup_deleted_events(calendar_event_ids):
    for job in scheduler.get_jobs():
        job_id: str = job.id

        if job_id.endswith(":start") or job_id.endswith(":end"):
            event_id = job_id.rsplit(":", 1)[0]

            if event_id not in calendar_event_ids:
                try:
                    logger.debug(f"Removing old event with id {event_id}")
                    scheduler.remove_job(job_id)
                except JobLookupError:
                    logger.error("Error while removing job", exc_info=True)


def get_next_events():
    event_ids = set()

    for event in get_events(getenv("EMAIL_TO_SEARCH", None), base_path):
        event_id = event['id']
        start = datetime.fromisoformat(event["start"].get("dateTime", event["start"].get("date")))
        end = datetime.fromisoformat(event["end"].get("dateTime", event["end"].get("date")))

        logger.debug(f"creating new job for event {event['summary']}, start: {start}, end: {end}")

        scheduler.add_job(
            run_event,
            trigger="date",
            id=f"{event_id}:start",
            run_date=start,
            kwargs={"switch": False},
            replace_existing=True
        )

        scheduler.add_job(
            run_event,
            trigger="date",
            id=f"{event_id}:end",
            run_date=end,
            kwargs={"switch": True},
            replace_existing=True
        )

        event_ids.add(event_id)
    
    cleanup_deleted_events(event_ids)


def main():
    scheduler.add_job(get_next_events, "interval", minutes=15)
    logger.debug("Press Ctrl+{} to exit".format("Break" if name == "nt" else "C"))

    try:
        scheduler.start()
    except:
        logger.debug("Exiting")
        return


if __name__ == "__main__":
    main()
