import logging
import signal
import sys
from types import FrameType

from apscheduler.schedulers.blocking import BlockingScheduler

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("mikos.worker")


def main() -> None:
    scheduler = BlockingScheduler(timezone=settings.tz)

    # M1 will register: hourly RRULE materialization.
    # M2 will register: nightly Garmin sync at 06:00.

    def _shutdown(signum: int, _frame: FrameType | None) -> None:
        log.info("received signal %s, shutting down", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    log.info("scheduler starting (tz=%s)", settings.tz)
    scheduler.start()


if __name__ == "__main__":
    main()
