import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.cf_access import require_user
from app.db.models import OccurrenceStatus, Task, TaskOccurrence
from app.db.session import get_db
from app.domain.users import get_or_create_user
from app.schemas.tasks import OccurrenceOut

router = APIRouter(prefix="/api/occurrences", tags=["occurrences"])


def _get_user_occurrence(db: Session, user_id: int, occurrence_id: int) -> TaskOccurrence:
    occ = db.scalar(
        select(TaskOccurrence)
        .options(joinedload(TaskOccurrence.task))
        .join(Task, TaskOccurrence.task_id == Task.id)
        .where(TaskOccurrence.id == occurrence_id, Task.user_id == user_id)
    )
    if occ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Occurrence not found")
    return occ


@router.post("/{occurrence_id}/complete", response_model=OccurrenceOut)
def complete_occurrence(
    occurrence_id: int,
    email: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> TaskOccurrence:
    user = get_or_create_user(db, email)
    occ = _get_user_occurrence(db, user.id, occurrence_id)
    occ.status = OccurrenceStatus.done
    occ.completed_at = dt.datetime.now(dt.UTC)
    db.commit()
    db.refresh(occ)
    return occ


@router.post("/{occurrence_id}/skip", response_model=OccurrenceOut)
def skip_occurrence(
    occurrence_id: int,
    email: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> TaskOccurrence:
    user = get_or_create_user(db, email)
    occ = _get_user_occurrence(db, user.id, occurrence_id)
    occ.status = OccurrenceStatus.skipped
    occ.completed_at = None
    db.commit()
    db.refresh(occ)
    return occ


@router.post("/{occurrence_id}/reopen", response_model=OccurrenceOut)
def reopen_occurrence(
    occurrence_id: int,
    email: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> TaskOccurrence:
    user = get_or_create_user(db, email)
    occ = _get_user_occurrence(db, user.id, occurrence_id)
    occ.status = OccurrenceStatus.pending
    occ.completed_at = None
    db.commit()
    db.refresh(occ)
    return occ
