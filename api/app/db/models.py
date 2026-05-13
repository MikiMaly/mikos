import datetime as dt
import enum

from sqlalchemy import (
    ARRAY,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TaskStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class OccurrenceStatus(str, enum.Enum):
    pending = "pending"
    done = "done"
    skipped = "skipped"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Europe/Prague")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    rrule: Mapped[str | None] = mapped_column(Text)
    rrule_start: Mapped[dt.date | None] = mapped_column(Date)
    rrule_end: Mapped[dt.date | None] = mapped_column(Date)

    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.active, index=True
    )

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    occurrences: Mapped[list["TaskOccurrence"]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class TaskOccurrence(Base):
    __tablename__ = "task_occurrences"
    __table_args__ = (UniqueConstraint("task_id", "occurs_on", name="uq_task_occurs"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurs_on: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    occurs_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[OccurrenceStatus] = mapped_column(
        SAEnum(OccurrenceStatus, name="occurrence_status"),
        nullable=False,
        default=OccurrenceStatus.pending,
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    task: Mapped[Task] = relationship(back_populates="occurrences")


__all__ = [
    "Base",
    "User",
    "Task",
    "TaskOccurrence",
    "TaskStatus",
    "OccurrenceStatus",
]
