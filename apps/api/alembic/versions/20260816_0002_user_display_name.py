"""Persist the optional user display name on agent runs.

Revision ID: 20260816_0002
Revises: 20260815_0001
Create Date: 2026-08-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_0002"
down_revision: str | None = "20260815_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_run", sa.Column("user_display_name", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_run", "user_display_name")
