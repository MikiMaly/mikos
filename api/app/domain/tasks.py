import datetime as dt
import logging

from dateutil.rrule import rrulestr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import OccurrenceStatus, Task, TaskOccurrence, TaskStatus

log = logging.getLogger(__name__)

MATERIALIZE_WINDOW_DAYS = 60


def expand_rrule(
    rrule_str: str,
    dtstart: dt.date,
    window_start: dt.date,
    window_end: dt.date,
) -> list[dt.date]:
    start_dt = dt.datetime.combine(dtstart, dt.time.min)
    rule = rrulestr(rrule_str, dtstart=start_dt)

    win_start = dt.datetime.combine(window_start, dt.time.min)
    win_end = dt.datetime.combine(window_end, dt.time.max)

    return [occ.date() for occ in rule.between(win_start, win_end, inc=True)]


def _target_dates(task: Task, today: dt.date, window_days: int) -> list[dt.date]:
    if task.status != TaskStatus.active:
        return []

    if task.due_at is not None:
        # One-off task: a single occurrence on its due date (even if in the past
        # — user may want to still see/complete it).
        return [task.due_at.date()]

    if task.rrule:
        window_end = today + dt.timedelta(days=window_days)
        dtstart = task.rrule_start or today
        rule_end = task.rrule_end or window_end
        effective_end = min(rule_end, window_end)
        if effective_end < today:
            return []
        return expand_rrule(task.rrule, dtstart, today, effective_end)

    return []


def materialize_task(
    db: Session,
    task: Task,
    *,
    today: dt.date | None = None,
    window_days: int = MATERIALIZE_WINDOW_DAYS,
) -> int:
    """Upsert pending occurrences for a task. Returns count of newly inserted rows.

    Idempotent: existing occurrences (any status) are left untouched.
    """
    today = today or dt.date.today()
    targets = _target_dates(task, today, window_days)
    if not targets:
        return 0

    existing_dates = set(
        db.scalars(
            select(TaskOccurrence.occurs_on).where(
                TaskOccurrence.task_id == task.id,
                TaskOccurrence.occurs_on.in_(targets),
            )
        ).all()
    )

    added = 0
    for occurs_on in targets:
        if occurs_on in existing_dates:
            continue
        occurs_at = task.due_at if task.due_at and task.due_at.date() == occurs_on else None
        db.add(
            TaskOccurrence(
                task_id=task.id,
                occurs_on=occurs_on,
                occurs_at=occurs_at,
                status=OccurrenceStatus.pending,
            )
        )
        added += 1

    return added


def regenerate_future_occurrences(
    db: Session,
    task: Task,
    *,
    today: dt.date | None = None,
) -> int:
    """Delete future pending occurrences for a task and re-materialize.

    Used when the task's schedule (rrule / due_at) changes. Done occurrences
    are preserved, as are past pending ones (user may still want to mark them).
    """
    today = today or dt.date.today()
    db.execute(
        delete(TaskOccurrence).where(
            TaskOccurrence.task_id == task.id,
            TaskOccurrence.occurs_on >= today,
            TaskOccurrence.status == OccurrenceStatus.pending,
        )
    )
    db.flush()
    return materialize_task(db, task, today=today)
