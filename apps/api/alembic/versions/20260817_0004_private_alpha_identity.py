"""Add private-alpha identity, quota, administration, and owned chat state.

Revision ID: 20260817_0004
Revises: 20260816_0003
Create Date: 2026-08-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260817_0004"
down_revision: str | None = "20260816_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "access_allowlist",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("role_on_registration", sa.String(24), nullable=True),
        sa.Column("claimed_by_user_id", sa.String(36), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "access_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("ip_pseudonym", sa.String(64), nullable=True),
        sa.Column("device_digest", sa.String(64), nullable=True),
        sa.Column("resolved_by_user_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_access_request_status_created", "access_request", ["status", "created_at"])
    op.create_table(
        "user_account",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("daily_run_limit", sa.Integer(), nullable=True),
        sa.Column("terms_version", sa.String(64), nullable=False),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_account_status", "user_account", ["status"])
    op.create_table(
        "password_credential",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "email_action_token",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_email_action_user_purpose",
        "email_action_token",
        ["user_id", "purpose", "created_at"],
    )
    op.create_index("ix_email_action_expiry", "email_action_token", ["expires_at"])
    op.create_table(
        "auth_session",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_digest", sa.String(64), nullable=False),
        sa.Column("device_digest", sa.String(64), nullable=True),
        sa.Column("ip_pseudonym", sa.String(64), nullable=True),
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_auth_session_user_active",
        "auth_session",
        ["user_id", "revoked_at", "idle_expires_at"],
    )
    op.create_index("ix_auth_session_expiry", "auth_session", ["absolute_expires_at"])
    op.create_table(
        "user_role",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(24), primary_key=True),
        sa.Column("granted_by_user_id", sa.String(36), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "admin_mfa",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("encrypted_secret", sa.Text(), nullable=False),
        sa.Column("recovery_code_hashes", sa.JSON(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "user_device",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("device_digest", sa.String(64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "device_digest", name="uq_user_device_digest"),
    )
    op.create_index("ix_user_device_last_seen", "user_device", ["last_seen_at"])
    op.create_table(
        "daily_usage_ledger",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("device_digest", sa.String(64), nullable=True),
        sa.Column("ip_pseudonym", sa.String(64), nullable=True),
        sa.Column("usage_day", sa.Date(), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("charged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("run_id", name="uq_daily_usage_run"),
    )
    op.create_index(
        "ix_daily_usage_user_day",
        "daily_usage_ledger",
        ["user_id", "usage_day", "status"],
    )
    op.create_index(
        "ix_daily_usage_device_day",
        "daily_usage_ledger",
        ["device_digest", "usage_day", "status"],
    )
    op.create_index(
        "ix_daily_usage_ip_day",
        "daily_usage_ledger",
        ["ip_pseudonym", "usage_day", "status"],
    )
    op.create_table(
        "daily_service_usage",
        sa.Column("usage_day", sa.Date(), primary_key=True),
        sa.Column("reserved_or_charged_units", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "daily_signal_usage",
        sa.Column("signal_type", sa.String(16), primary_key=True),
        sa.Column("signal_digest", sa.String(64), primary_key=True),
        sa.Column("usage_day", sa.Date(), primary_key=True),
        sa.Column("reserved_or_charged_units", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "quota_grant",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("valid_on", sa.Date(), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(240), nullable=True),
        sa.Column("created_by_user_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_quota_grant_user_day", "quota_grant", ["user_id", "valid_on"])
    op.create_table(
        "quota_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("requested_units", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("resolved_by_user_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_quota_request_user_status",
        "quota_request",
        ["user_id", "status", "created_at"],
    )
    op.create_index("ix_quota_request_status_created", "quota_request", ["status", "created_at"])
    op.create_table(
        "rate_limit_bucket",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("subject_digest", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("action", "subject_digest", "window_start", name="uq_rate_bucket"),
    )
    op.create_index("ix_rate_bucket_expiry", "rate_limit_bucket", ["expires_at"])
    op.create_table(
        "audit_event",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", sa.String(36), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(48), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("ip_pseudonym", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_event_created", "audit_event", ["created_at"])
    op.create_table(
        "user_conversation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("title_state", sa.String(24), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("terminated", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_conversation_updated", "user_conversation", ["user_id", "updated_at"])
    op.create_table(
        "user_conversation_message",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("user_conversation.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("conversation_id", "ordinal", name="uq_user_conversation_ordinal"),
    )
    op.create_index(
        "ix_user_conversation_message",
        "user_conversation_message",
        ["conversation_id", "ordinal"],
    )
    op.create_table(
        "user_preference",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("user_account.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.String(32), nullable=True),
        sa.Column("theme_id", sa.String(48), nullable=True),
        sa.Column("sidebar_width", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    with op.batch_alter_table("conversation_message_control") as batch:
        batch.add_column(sa.Column("user_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("auth_session_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_message_control_user", "user_account", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch.create_foreign_key(
            "fk_message_control_auth_session",
            "auth_session",
            ["auth_session_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_message_user_conversation",
        "conversation_message_control",
        ["user_id", "conversation_id", "active"],
    )

    with op.batch_alter_table("agent_run") as batch:
        batch.add_column(sa.Column("user_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("auth_session_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_agent_run_user", "user_account", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch.create_foreign_key(
            "fk_agent_run_auth_session",
            "auth_session",
            ["auth_session_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_unique_constraint("uq_run_user_idempotency", ["user_id", "idempotency_key"])
    op.create_index("ix_run_user", "agent_run", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_run_user", table_name="agent_run")
    with op.batch_alter_table("agent_run") as batch:
        batch.drop_constraint("uq_run_user_idempotency", type_="unique")
        batch.drop_constraint("fk_agent_run_auth_session", type_="foreignkey")
        batch.drop_constraint("fk_agent_run_user", type_="foreignkey")
        batch.drop_column("auth_session_id")
        batch.drop_column("user_id")
    op.drop_index("ix_message_user_conversation", table_name="conversation_message_control")
    with op.batch_alter_table("conversation_message_control") as batch:
        batch.drop_constraint("fk_message_control_auth_session", type_="foreignkey")
        batch.drop_constraint("fk_message_control_user", type_="foreignkey")
        batch.drop_column("auth_session_id")
        batch.drop_column("user_id")

    op.drop_table("user_preference")
    op.drop_index("ix_user_conversation_message", table_name="user_conversation_message")
    op.drop_table("user_conversation_message")
    op.drop_index("ix_user_conversation_updated", table_name="user_conversation")
    op.drop_table("user_conversation")
    op.drop_index("ix_audit_event_created", table_name="audit_event")
    op.drop_table("audit_event")
    op.drop_index("ix_rate_bucket_expiry", table_name="rate_limit_bucket")
    op.drop_table("rate_limit_bucket")
    op.drop_index("ix_quota_request_status_created", table_name="quota_request")
    op.drop_index("ix_quota_request_user_status", table_name="quota_request")
    op.drop_table("quota_request")
    op.drop_index("ix_quota_grant_user_day", table_name="quota_grant")
    op.drop_table("quota_grant")
    op.drop_table("daily_signal_usage", if_exists=True)
    op.drop_table("daily_service_usage")
    op.drop_index("ix_daily_usage_ip_day", table_name="daily_usage_ledger", if_exists=True)
    op.drop_index("ix_daily_usage_device_day", table_name="daily_usage_ledger", if_exists=True)
    op.drop_index("ix_daily_usage_user_day", table_name="daily_usage_ledger")
    op.drop_table("daily_usage_ledger")
    op.drop_index("ix_user_device_last_seen", table_name="user_device")
    op.drop_table("user_device")
    op.drop_table("admin_mfa")
    op.drop_table("user_role")
    op.drop_index("ix_auth_session_expiry", table_name="auth_session")
    op.drop_index("ix_auth_session_user_active", table_name="auth_session")
    op.drop_table("auth_session")
    op.drop_index("ix_email_action_expiry", table_name="email_action_token")
    op.drop_index("ix_email_action_user_purpose", table_name="email_action_token")
    op.drop_table("email_action_token")
    op.drop_table("password_credential")
    op.drop_index("ix_user_account_status", table_name="user_account")
    op.drop_table("user_account")
    op.drop_index("ix_access_request_status_created", table_name="access_request")
    op.drop_table("access_request")
    op.drop_table("access_allowlist")
