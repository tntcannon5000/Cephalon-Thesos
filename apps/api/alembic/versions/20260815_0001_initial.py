"""Initial alpha runtime schema.

Revision ID: 20260815_0001
Revises:
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260815_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation_message_control",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("safety_action", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("conversation_id", "ordinal", name="uq_message_ordinal"),
    )
    op.create_index(
        "ix_message_active_safety",
        "conversation_message_control",
        ["conversation_id", "active", "safety_action"],
    )

    op.create_table(
        "agent_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), nullable=False),
        sa.Column("user_message_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("history_json", sa.JSON(), nullable=False),
        sa.Column("answer_text", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_run_idempotency"),
    )
    op.create_index("ix_run_session", "agent_run", ["session_id", "created_at"])
    op.create_index("ix_run_conversation", "agent_run", ["conversation_id", "created_at"])

    op.create_table(
        "agent_event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_run.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_event_sequence"),
    )
    op.create_index("ix_event_replay", "agent_event", ["run_id", "sequence"])

    op.create_table(
        "provider_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("request_tokens", sa.Integer(), nullable=True),
        sa.Column("response_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_run.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("provider_usage")
    op.drop_index("ix_event_replay", table_name="agent_event")
    op.drop_table("agent_event")
    op.drop_index("ix_run_conversation", table_name="agent_run")
    op.drop_index("ix_run_session", table_name="agent_run")
    op.drop_table("agent_run")
    op.drop_index("ix_message_active_safety", table_name="conversation_message_control")
    op.drop_table("conversation_message_control")
