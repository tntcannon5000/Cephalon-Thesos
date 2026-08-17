from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.engine import CursorResult

from veris_api.db.models import (
    AgentEvent,
    AgentRun,
    AuditEvent,
    AuthSession,
    DailyServiceUsage,
    DailySignalUsage,
    DailyUsageLedger,
    EmailActionToken,
    MessageControl,
    QuotaGrant,
    QuotaRequest,
    RateLimitBucket,
    RuntimeWorker,
    UserDevice,
)
from veris_api.db.repository import TERMINAL_RUN_STATUSES
from veris_api.db.session import get_session_factory


async def purge_expired_runs(*, now: datetime | None = None) -> list[str]:
    cutoff = now or datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        raw_content_cutoff = cutoff - timedelta(hours=24)
        expired_content_run_ids = select(AgentRun.id).where(
            AgentRun.status.in_(TERMINAL_RUN_STATUSES),
            AgentRun.updated_at <= raw_content_cutoff,
        )
        await session.execute(
            delete(AgentEvent).where(AgentEvent.run_id.in_(expired_content_run_ids))
        )
        await session.execute(
            update(AgentRun)
            .where(
                AgentRun.status.in_(TERMINAL_RUN_STATUSES),
                AgentRun.updated_at <= raw_content_cutoff,
            )
            .values(request_text="", history_json=[], answer_text=None)
        )
        rows = list(
            await session.execute(
                select(AgentRun.id, AgentRun.user_message_id).where(
                    AgentRun.status.in_(TERMINAL_RUN_STATUSES),
                    AgentRun.expires_at <= cutoff,
                )
            )
        )
        if not rows:
            return []
        run_ids = [row.id for row in rows]
        message_ids = [row.user_message_id for row in rows]
        await session.execute(delete(MessageControl).where(MessageControl.id.in_(message_ids)))
        await session.execute(delete(AgentRun).where(AgentRun.id.in_(run_ids)))
        return run_ids


async def purge_expired_security_data(*, now: datetime | None = None) -> None:
    cutoff = now or datetime.now(UTC)
    thirty_days_ago = cutoff - timedelta(days=30)
    ninety_days_ago = cutoff - timedelta(days=90)
    audit_cutoff = cutoff - timedelta(days=180)
    async with get_session_factory()() as session, session.begin():
        await session.execute(delete(EmailActionToken).where(EmailActionToken.expires_at < cutoff))
        await session.execute(delete(RateLimitBucket).where(RateLimitBucket.expires_at < cutoff))
        await session.execute(delete(UserDevice).where(UserDevice.last_seen_at < thirty_days_ago))
        await session.execute(
            delete(AuthSession).where(
                or_(
                    AuthSession.absolute_expires_at < thirty_days_ago,
                    and_(
                        AuthSession.revoked_at.is_not(None),
                        AuthSession.revoked_at < thirty_days_ago,
                    ),
                )
            )
        )
        await session.execute(
            delete(DailyUsageLedger).where(DailyUsageLedger.reserved_at < ninety_days_ago)
        )
        await session.execute(
            delete(DailyServiceUsage).where(DailyServiceUsage.usage_day < ninety_days_ago.date())
        )
        await session.execute(
            delete(DailySignalUsage).where(DailySignalUsage.usage_day < ninety_days_ago.date())
        )
        await session.execute(
            delete(QuotaGrant).where(QuotaGrant.valid_on < ninety_days_ago.date())
        )
        await session.execute(
            delete(QuotaRequest).where(
                QuotaRequest.resolved_at.is_not(None),
                QuotaRequest.resolved_at < ninety_days_ago,
            )
        )
        await session.execute(delete(AuditEvent).where(AuditEvent.created_at < audit_cutoff))


async def purge_stale_workers(*, now: datetime | None = None) -> int:
    cutoff = (now or datetime.now(UTC)) - timedelta(days=1)
    async with get_session_factory()() as session, session.begin():
        result = cast(
            CursorResult[Any],
            await session.execute(
                delete(RuntimeWorker).where(RuntimeWorker.last_heartbeat_at < cutoff)
            ),
        )
        return result.rowcount or 0
