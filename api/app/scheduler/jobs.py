import logging

from sqlalchemy import select

from app.db.models import Task, TaskStatus
from app.db.session import SessionLocal
from app.domain.tasks import materialize_task

log = logging.getLogger("mikos.worker.jobs")


def materialize_all_active_tasks() -> None:
    try:
        with SessionLocal() as db:
            tasks = list(
                db.scalars(select(Task).where(Task.status == TaskStatus.active)).all()
            )
            total = 0
            for task in tasks:
                total += materialize_task(db, task)
            db.commit()
        log.info("materialize: %d tasks scanned, %d new occurrences", len(tasks), total)
    except Exception:
        log.exception("materialize failed")
