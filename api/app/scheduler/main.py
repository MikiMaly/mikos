import logging
import signal
import sys
from types import FrameType

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import settings
from app.scheduler.jobs import materialize_all_active_tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("mikos.worker")


def main() -> None:
    scheduler = BlockingScheduler(timezone=settings.tz)

    scheduler.add_job(
        materialize_all_active_tasks,
        trigger="cron",
        minute=5,
        id="materialize_occurrences",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # M2 will register the nightly Garmin sync at 06:00 here.

    def _shutdown(signum: int, _frame: FrameType | None) -> None:
        log.info("received signal %s, shutting down", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("scheduler starting (tz=%s)", settings.tz)
    # Run once on startup so fresh containers materialize occurrences immediately.
    materialize_all_active_tasks()
    scheduler.start()


if __name__ == "__main__":
    main()
