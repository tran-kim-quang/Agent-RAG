"""add multi-turn chat runs and knowledge base version

Revision ID: 9f42b7a16c31
Revises: 7caef33dd667
Create Date: 2026-07-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9f42b7a16c31"
down_revision: Union[str, Sequence[str], None] = "7caef33dd667"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("knowledge_base_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_table(
        "chat_runs",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("session_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("events", sa.JSON(), nullable=False),
        sa.Column("task_id", sa.String(length=50), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_chat_runs_session_id"), "chat_runs", ["session_id"], unique=False)
    op.create_index(op.f("ix_chat_runs_status"), "chat_runs", ["status"], unique=False)
    op.create_index(op.f("ix_chat_runs_task_id"), "chat_runs", ["task_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_runs_task_id"), table_name="chat_runs")
    op.drop_index(op.f("ix_chat_runs_status"), table_name="chat_runs")
    op.drop_index(op.f("ix_chat_runs_session_id"), table_name="chat_runs")
    op.drop_table("chat_runs")
    op.drop_column("users", "knowledge_base_version")
