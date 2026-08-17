"""Add the hosted-alpha dispatch, accounting, and retention substrate.

Revision ID: 20260816_0003
Revises: 20260816_0002
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_0003"
down_revision: str | None = "20260816_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agent_run") as batch:
        batch.add_column(
            sa.Column("last_event_sequence", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(
            sa.Column("dispatch_attempts", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("lease_owner", sa.String(128), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(
            sa.Column(
                "next_attempt_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.add_column(
            sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "expires_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )

    op.execute(
        sa.text(
            """
            UPDATE agent_run
            SET last_event_sequence = COALESCE(
                (SELECT MAX(agent_event.sequence)
                 FROM agent_event
                 WHERE agent_event.run_id = agent_run.id),
                0
            )
            """
        )
    )
    op.create_index(
        "ix_run_dispatch",
        "agent_run",
        ["status", "next_attempt_at", "lease_expires_at"],
    )
    op.create_index("ix_run_expiry", "agent_run", ["expires_at"])

    with op.batch_alter_table("provider_usage") as batch:
        batch.alter_column("model", new_column_name="requested_model")
        batch.add_column(sa.Column("attempt_index", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("provider", sa.String(64), nullable=False, server_default="openrouter")
        )
        batch.add_column(sa.Column("resolved_model", sa.String(128), nullable=True))
        batch.add_column(
            sa.Column("status", sa.String(32), nullable=False, server_default="succeeded")
        )
        batch.add_column(sa.Column("total_tokens", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("estimated_cost_usd", sa.Numeric(12, 8), nullable=True))
        batch.add_column(sa.Column("latency_ms", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("cancellation_point", sa.String(64), nullable=True))
        batch.add_column(sa.Column("error_code", sa.String(64), nullable=True))
        batch.add_column(sa.Column("provider_request_id", sa.String(128), nullable=True))
        batch.add_column(
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch.add_column(
            sa.Column(
                "started_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            )
        )
        batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(sa.text("UPDATE provider_usage SET attempt_index = id WHERE attempt_index IS NULL"))
    with op.batch_alter_table("provider_usage") as batch:
        batch.alter_column("attempt_index", nullable=False)
        batch.create_unique_constraint("uq_provider_attempt", ["run_id", "attempt_index"])
    op.create_index("ix_provider_usage_run", "provider_usage", ["run_id", "attempt_index"])
    op.create_index("ix_provider_usage_created", "provider_usage", ["created_at"])

    op.create_table(
        "runtime_worker",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("active_runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_runtime_worker_heartbeat", "runtime_worker", ["last_heartbeat_at"])


def downgrade() -> None:
    op.drop_index("ix_runtime_worker_heartbeat", table_name="runtime_worker")
    op.drop_table("runtime_worker")

    op.drop_index("ix_provider_usage_created", table_name="provider_usage")
    op.drop_index("ix_provider_usage_run", table_name="provider_usage")
    with op.batch_alter_table("provider_usage") as batch:
        batch.drop_constraint("uq_provider_attempt", type_="unique")
        batch.drop_column("completed_at")
        batch.drop_column("started_at")
        batch.drop_column("metadata_json")
        batch.drop_column("provider_request_id")
        batch.drop_column("error_code")
        batch.drop_column("cancellation_point")
        batch.drop_column("latency_ms")
        batch.drop_column("estimated_cost_usd")
        batch.drop_column("total_tokens")
        batch.drop_column("status")
        batch.drop_column("resolved_model")
        batch.drop_column("provider")
        batch.drop_column("attempt_index")
        batch.alter_column("requested_model", new_column_name="model")

    op.drop_index("ix_run_expiry", table_name="agent_run")
    op.drop_index("ix_run_dispatch", table_name="agent_run")
    with op.batch_alter_table("agent_run") as batch:
        batch.drop_column("expires_at")
        batch.drop_column("cancel_requested_at")
        batch.drop_column("next_attempt_at")
        batch.drop_column("lease_expires_at")
        batch.drop_column("lease_owner")
        batch.drop_column("dispatch_attempts")
        batch.drop_column("last_event_sequence")
