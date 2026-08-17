from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class AccessAllowlist(Base):
    __tablename__ = "access_allowlist"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    role_on_registration: Mapped[str | None] = mapped_column(String(24))
    claimed_by_user_id: Mapped[str | None] = mapped_column(String(36))
    created_by_user_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccessRequest(Base):
    __tablename__ = "access_request"
    __table_args__ = (Index("ix_access_request_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    ip_pseudonym: Mapped[str | None] = mapped_column(String(64))
    device_digest: Mapped[str | None] = mapped_column(String(64))
    resolved_by_user_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UserAccount(Base):
    __tablename__ = "user_account"
    __table_args__ = (Index("ix_user_account_status", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    daily_run_limit: Mapped[int | None] = mapped_column(Integer)
    terms_version: Mapped[str] = mapped_column(String(64), nullable=False)
    terms_accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PasswordCredential(Base):
    __tablename__ = "password_credential"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EmailActionToken(Base):
    __tablename__ = "email_action_token"
    __table_args__ = (
        Index("ix_email_action_user_purpose", "user_id", "purpose", "created_at"),
        Index("ix_email_action_expiry", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuthSession(Base):
    __tablename__ = "auth_session"
    __table_args__ = (
        Index("ix_auth_session_user_active", "user_id", "revoked_at", "idle_expires_at"),
        Index("ix_auth_session_expiry", "absolute_expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    token_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    device_digest: Mapped[str | None] = mapped_column(String(64))
    ip_pseudonym: Mapped[str | None] = mapped_column(String(64))
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(64))


class UserRole(Base):
    __tablename__ = "user_role"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(24), primary_key=True)
    granted_by_user_id: Mapped[str | None] = mapped_column(String(36))
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AdminMFA(Base):
    __tablename__ = "admin_mfa"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True
    )
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    recovery_code_hashes: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UserDevice(Base):
    __tablename__ = "user_device"
    __table_args__ = (
        UniqueConstraint("user_id", "device_digest", name="uq_user_device_digest"),
        Index("ix_user_device_last_seen", "last_seen_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    device_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DailyUsageLedger(Base):
    __tablename__ = "daily_usage_ledger"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_daily_usage_run"),
        Index("ix_daily_usage_user_day", "user_id", "usage_day", "status"),
        Index("ix_daily_usage_device_day", "device_digest", "usage_day", "status"),
        Index("ix_daily_usage_ip_day", "ip_pseudonym", "usage_day", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    run_id: Mapped[str] = mapped_column(String(36), nullable=False)
    device_digest: Mapped[str | None] = mapped_column(String(64))
    ip_pseudonym: Mapped[str | None] = mapped_column(String(64))
    usage_day: Mapped[date] = mapped_column(Date, nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    charged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DailyServiceUsage(Base):
    __tablename__ = "daily_service_usage"

    usage_day: Mapped[date] = mapped_column(Date, primary_key=True)
    reserved_or_charged_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class DailySignalUsage(Base):
    __tablename__ = "daily_signal_usage"

    signal_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    signal_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    usage_day: Mapped[date] = mapped_column(Date, primary_key=True)
    reserved_or_charged_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class QuotaGrant(Base):
    __tablename__ = "quota_grant"
    __table_args__ = (Index("ix_quota_grant_user_day", "user_id", "valid_on"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    valid_on: Mapped[date] = mapped_column(Date, nullable=False)
    units: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(240))
    created_by_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class QuotaRequest(Base):
    __tablename__ = "quota_request"
    __table_args__ = (
        Index("ix_quota_request_user_status", "user_id", "status", "created_at"),
        Index("ix_quota_request_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    requested_units: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    resolved_by_user_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_bucket"
    __table_args__ = (
        UniqueConstraint("action", "subject_digest", "window_start", name="uq_rate_bucket"),
        Index("ix_rate_bucket_expiry", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    subject_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AuditEvent(Base):
    __tablename__ = "audit_event"
    __table_args__ = (Index("ix_audit_event_created", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(48), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ip_pseudonym: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConversationRecord(Base):
    __tablename__ = "user_conversation"
    __table_args__ = (Index("ix_user_conversation_updated", "user_id", "updated_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    title_state: Mapped[str] = mapped_column(String(24), nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    terminated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConversationMessageRecord(Base):
    __tablename__ = "user_conversation_message"
    __table_args__ = (
        UniqueConstraint("conversation_id", "ordinal", name="uq_user_conversation_ordinal"),
        Index("ix_user_conversation_message", "conversation_id", "ordinal"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("user_conversation.id", ondelete="CASCADE")
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="complete")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UserPreference(Base):
    __tablename__ = "user_preference"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_account.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str | None] = mapped_column(String(32))
    theme_id: Mapped[str | None] = mapped_column(String(48))
    sidebar_width: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MessageControl(Base):
    __tablename__ = "conversation_message_control"
    __table_args__ = (
        UniqueConstraint("conversation_id", "ordinal", name="uq_message_ordinal"),
        Index("ix_message_active_safety", "conversation_id", "active", "safety_action"),
        Index("ix_message_user_conversation", "user_id", "conversation_id", "active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    auth_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("auth_session.id", ondelete="SET NULL")
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    safety_action: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentRun(Base):
    __tablename__ = "agent_run"
    __table_args__ = (
        UniqueConstraint("session_id", "idempotency_key", name="uq_run_idempotency"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_run_user_idempotency"),
        Index("ix_run_session", "session_id", "created_at"),
        Index("ix_run_user", "user_id", "created_at"),
        Index("ix_run_conversation", "conversation_id", "created_at"),
        Index("ix_run_dispatch", "status", "next_attempt_at", "lease_expires_at"),
        Index("ix_run_expiry", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_message_id: Mapped[str] = mapped_column(String(36), nullable=False)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("user_account.id", ondelete="CASCADE"))
    auth_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("auth_session.id", ondelete="SET NULL")
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    user_display_name: Mapped[str | None] = mapped_column(String(32))
    history_json: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    answer_text: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))
    last_event_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dispatch_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: utc_now() + timedelta(days=30)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AgentEvent(Base):
    __tablename__ = "agent_event"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_event_sequence"),
        Index("ix_event_replay", "run_id", "sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_run.id", ondelete="CASCADE"))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProviderUsage(Base):
    __tablename__ = "provider_usage"
    __table_args__ = (
        UniqueConstraint("run_id", "attempt_index", name="uq_provider_attempt"),
        Index("ix_provider_usage_run", "run_id", "attempt_index"),
        Index("ix_provider_usage_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_run.id", ondelete="CASCADE"))
    attempt_index: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    requested_model: Mapped[str] = mapped_column(String(128), nullable=False)
    resolved_model: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    request_tokens: Mapped[int | None] = mapped_column(Integer)
    response_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cancellation_point: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    provider_request_id: Mapped[str | None] = mapped_column(String(128))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RuntimeWorker(Base):
    __tablename__ = "runtime_worker"
    __table_args__ = (Index("ix_runtime_worker_heartbeat", "last_heartbeat_at"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    active_runs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
