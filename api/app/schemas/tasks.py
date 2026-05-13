import datetime as dt

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import OccurrenceStatus, TaskStatus


class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    priority: int = 0
    tags: list[str] = Field(default_factory=list)
    due_at: dt.datetime | None = None
    rrule: str | None = None
    rrule_start: dt.date | None = None
    rrule_end: dt.date | None = None


class TaskCreate(TaskBase):
    @model_validator(mode="after")
    def _exactly_one_schedule(self) -> "TaskCreate":
        if self.due_at and self.rrule:
            raise ValueError("Task must have either due_at or rrule, not both")
        if not self.due_at and not self.rrule:
            raise ValueError("Task must have either due_at or rrule")
        return self


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    priority: int | None = None
    tags: list[str] | None = None
    due_at: dt.datetime | None = None
    rrule: str | None = None
    rrule_start: dt.date | None = None
    rrule_end: dt.date | None = None
    status: TaskStatus | None = None


class TaskOut(TaskBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: TaskStatus
    created_at: dt.datetime
    updated_at: dt.datetime


class TaskMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    priority: int
    tags: list[str]


class OccurrenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    occurs_on: dt.date
    occurs_at: dt.datetime | None
    status: OccurrenceStatus
    completed_at: dt.datetime | None
    notes: str | None
    task: TaskMini


class TodayResponse(BaseModel):
    date: dt.date
    tasks: list[OccurrenceOut]
    sleep: dict | None = None  # populated in M2
