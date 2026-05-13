from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.cf_access import require_user
from app.db.models import Task, TaskStatus
from app.db.session import get_db
from app.domain.tasks import materialize_task, regenerate_future_occurrences
from app.domain.users import get_or_create_user
from app.schemas.tasks import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

_SCHEDULE_FIELDS = {"due_at", "rrule", "rrule_start", "rrule_end"}


@router.get("", response_model=list[TaskOut])
def list_tasks(
    status_filter: TaskStatus | None = None,
    email: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> list[Task]:
    user = get_or_create_user(db, email)
    db.commit()  # persist user creation
    q = select(Task).where(Task.user_id == user.id)
    if status_filter is not None:
        q = q.where(Task.status == status_filter)
    return list(db.scalars(q.order_by(Task.created_at.desc())).all())


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    data: TaskCreate,
    email: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> Task:
    user = get_or_create_user(db, email)
    task = Task(user_id=user.id, **data.model_dump())
    db.add(task)
    db.flush()
    materialize_task(db, task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    data: TaskUpdate,
    email: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> Task:
    user = get_or_create_user(db, email)
    task = db.get(Task, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")

    changes = data.model_dump(exclude_unset=True)
    schedule_changed = any(field in changes for field in _SCHEDULE_FIELDS)

    for key, value in changes.items():
        setattr(task, key, value)
    db.flush()

    if schedule_changed:
        regenerate_future_occurrences(db, task)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    email: str = Depends(require_user),
    db: Session = Depends(get_db),
) -> None:
    user = get_or_create_user(db, email)
    task = db.get(Task, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Task not found")
    db.delete(task)
    db.commit()
