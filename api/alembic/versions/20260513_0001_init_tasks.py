"""init tasks

Revision ID: 0001
Revises:
Create Date: 2026-05-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Europe/Prague"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    task_status = sa.Enum("active", "archived", name="task_status")
    task_status.create(op.get_bind(), checkfirst=True)

    occurrence_status = sa.Enum("pending", "done", "skipped", name="occurrence_status")
    occurrence_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "tags",
            sa.ARRAY(sa.String),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("rrule", sa.Text),
        sa.Column("rrule_start", sa.Date),
        sa.Column("rrule_end", sa.Date),
        sa.Column(
            "status",
            sa.Enum("active", "archived", name="task_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "task_occurrences",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "task_id",
            sa.Integer,
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("occurs_on", sa.Date, nullable=False),
        sa.Column("occurs_at", sa.DateTime(timezone=True)),
        sa.Column(
            "status",
            sa.Enum("pending", "done", "skipped", name="occurrence_status", create_type=False),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("task_id", "occurs_on", name="uq_task_occurs"),
    )
    op.create_index("ix_task_occurrences_task_id", "task_occurrences", ["task_id"])
    op.create_index("ix_task_occurrences_occurs_on", "task_occurrences", ["occurs_on"])


def downgrade() -> None:
    op.drop_index("ix_task_occurrences_occurs_on", table_name="task_occurrences")
    op.drop_index("ix_task_occurrences_task_id", table_name="task_occurrences")
    op.drop_table("task_occurrences")
    op.drop_index("ix_tasks_status", table_name="tasks")
    op.drop_index("ix_tasks_user_id", table_name="tasks")
    op.drop_table("tasks")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    sa.Enum(name="occurrence_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="task_status").drop(op.get_bind(), checkfirst=True)
