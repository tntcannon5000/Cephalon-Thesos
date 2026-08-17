from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select

from veris_api.config import get_settings
from veris_api.db.models import AgentEvent, AgentRun, RuntimeWorker
from veris_api.db.session import get_session_factory


@dataclass(frozen=True)
class ClaimedRun:
    run_id: str
    dispatch_attempt: int


def _append_event(run: AgentRun, event_type: str, payload: dict[str, object]) -> AgentEvent:
    run.last_event_sequence += 1
    return AgentEvent(
        run_id=run.id,
        sequence=run.last_event_sequence,
        event_type=event_type,
        payload=payload,
        created_at=datetime.now(UTC),
    )


async def claim_next_run(worker_id: str) -> ClaimedRun | None:
    settings = get_settings()
    now = datetime.now(UTC)
    expired_lease = and_(
        AgentRun.status.in_(("dispatched", "working")),
        AgentRun.lease_expires_at.is_not(None),
        AgentRun.lease_expires_at <= now,
    )
    ready_run = and_(
        AgentRun.status == "accepted",
        AgentRun.next_attempt_at <= now,
    )
    async with get_session_factory()() as session, session.begin():
        run = await session.scalar(
            select(AgentRun)
            .where(
                or_(ready_run, expired_lease),
                AgentRun.cancel_requested_at.is_(None),
                AgentRun.dispatch_attempts < settings.worker_max_dispatch_attempts,
            )
            .order_by(AgentRun.next_attempt_at, AgentRun.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if run is None:
            return None
        run.status = "dispatched"
        run.dispatch_attempts += 1
        run.lease_owner = worker_id
        run.lease_expires_at = now + timedelta(seconds=settings.worker_lease_seconds)
        run.updated_at = now
        return ClaimedRun(run.id, run.dispatch_attempts)


async def renew_run_lease(run_id: str, worker_id: str) -> bool:
    settings = get_settings()
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        run = await session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if (
            run is None
            or run.lease_owner != worker_id
            or run.status not in {"dispatched", "working"}
        ):
            return False
        run.lease_expires_at = now + timedelta(seconds=settings.worker_lease_seconds)
        run.updated_at = now
        return True


async def cancellation_requested(run_id: str) -> bool:
    async with get_session_factory()() as session:
        value = await session.scalar(
            select(AgentRun.cancel_requested_at).where(AgentRun.id == run_id)
        )
        return value is not None


async def release_run_for_retry(run_id: str, worker_id: str, error_code: str) -> None:
    settings = get_settings()
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        run = await session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None or run.lease_owner != worker_id:
            return
        run.lease_owner = None
        run.lease_expires_at = None
        run.updated_at = now
        if run.dispatch_attempts >= settings.worker_max_dispatch_attempts:
            run.status = "failed"
            run.error_code = error_code
            session.add(
                _append_event(
                    run,
                    "run.failed",
                    {
                        "code": error_code,
                        "message": (
                            "The Archives could not be reached. "
                            "Your message has been kept for retry."
                        ),
                    },
                )
            )
            return

        delay_seconds = min(30, 2 ** max(0, run.dispatch_attempts - 1))
        run.status = "accepted"
        run.next_attempt_at = now + timedelta(seconds=delay_seconds)
        session.add(
            _append_event(
                run,
                "status.changed",
                {"kind": "queued", "label": "Reconnecting"},
            )
        )


async def heartbeat_worker(worker_id: str, active_runs: int, *, status: str = "ready") -> None:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        worker = await session.get(RuntimeWorker, worker_id)
        if worker is None:
            session.add(
                RuntimeWorker(
                    id=worker_id,
                    status=status,
                    active_runs=active_runs,
                    started_at=now,
                    last_heartbeat_at=now,
                )
            )
            return
        worker.status = status
        worker.active_runs = active_runs
        worker.last_heartbeat_at = now


async def worker_is_live(max_age_seconds: int = 15) -> bool:
    cutoff = datetime.now(UTC) - timedelta(seconds=max_age_seconds)
    async with get_session_factory()() as session:
        worker_id = await session.scalar(
            select(RuntimeWorker.id)
            .where(
                RuntimeWorker.status == "ready",
                RuntimeWorker.last_heartbeat_at >= cutoff,
            )
            .order_by(RuntimeWorker.last_heartbeat_at.desc())
            .limit(1)
        )
        return worker_id is not None
