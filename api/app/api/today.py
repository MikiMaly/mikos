import datetime as dt

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.cf_access import require_user
from app.db.models import Task, TaskOccurrence
from app.db.session import get_db
from app.domain.users import get_or_create_user
from app.schemas.tasks import OccurrenceOut, TodayResponse

router = APIRouter(prefix="/api", tags=["today"])


@router.get("/today", response_model=TodayResponse)
def today(
    email: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> TodayResponse:
    user = get_or_create_user(db, email)
    db.commit()

    today_date = dt.date.today()

    occurrences = list(
        db.scalars(
            select(TaskOccurrence)
            .options(joinedload(TaskOccurrence.task))
            .join(Task, TaskOccurrence.task_id == Task.id)
            .where(
                Task.user_id == user.id,
                TaskOccurrence.occurs_on == today_date,
            )
            .order_by(
                TaskOccurrence.occurs_at.asc().nulls_first(),
                Task.priority.desc(),
                TaskOccurrence.id.asc(),
            )
        ).all()
    )

    return TodayResponse(
        date=today_date,
        tasks=[OccurrenceOut.model_validate(o) for o in occurrences],
        sleep=None,
    )
