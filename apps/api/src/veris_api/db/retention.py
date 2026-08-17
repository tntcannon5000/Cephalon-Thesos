from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult

from veris_api.db.models import AgentRun, MessageControl, RuntimeWorker
from veris_api.db.repository import TERMINAL_RUN_STATUSES
from veris_api.db.session import get_session_factory


async def purge_expired_runs(*, now: datetime | None = None) -> list[str]:
    cutoff = now or datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
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
