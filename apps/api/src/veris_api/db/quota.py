from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from veris_api.config import Settings, get_settings
from veris_api.db.models import (
    AgentRun,
    AuthSession,
    DailyServiceUsage,
    DailySignalUsage,
    DailyUsageLedger,
    QuotaGrant,
    QuotaRequest,
    UserAccount,
)
from veris_api.db.session import get_session_factory


class QuotaExceededError(Exception):
    pass


class ConcurrentRunLimitError(Exception):
    pass


@dataclass(frozen=True)
class Allowance:
    day: date
    limit: int
    used: int
    remaining: int
    reset_at: datetime


def utc_day(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).date()


def next_utc_midnight(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, tzinfo=UTC)


async def _locked_signal_usage(
    session: AsyncSession,
    signal_type: str,
    signal_digest: str,
    day: date,
    now: datetime,
) -> DailySignalUsage:
    values = {
        "signal_type": signal_type,
        "signal_digest": signal_digest,
        "usage_day": day,
        "reserved_or_charged_units": 0,
        "updated_at": now,
    }
    dialect_name = session.get_bind().dialect.name
    if dialect_name == "postgresql":
        create_counter = postgresql_insert(DailySignalUsage).values(**values)
    elif dialect_name == "sqlite":
        create_counter = sqlite_insert(DailySignalUsage).values(**values)
    else:
        raise RuntimeError(f"Unsupported database dialect: {dialect_name}")
    create_counter = create_counter.on_conflict_do_nothing(
        index_elements=["signal_type", "signal_digest", "usage_day"]
    )
    await session.execute(create_counter)
    counter = await session.scalar(
        select(DailySignalUsage)
        .where(
            DailySignalUsage.signal_type == signal_type,
            DailySignalUsage.signal_digest == signal_digest,
            DailySignalUsage.usage_day == day,
        )
        .with_for_update()
    )
    if counter is None:
        raise RuntimeError("Could not initialize daily signal usage")
    return counter


async def allowance_for_user(
    user_id: str,
    *,
    settings: Settings | None = None,
    day: date | None = None,
) -> Allowance:
    runtime = settings or get_settings()
    target_day = day or utc_day()
    async with get_session_factory()() as session:
        account = await session.get(UserAccount, user_id)
        if account is None:
            raise RuntimeError("Account not found")
        grant_units = await session.scalar(
            select(func.coalesce(func.sum(QuotaGrant.units), 0)).where(
                QuotaGrant.user_id == user_id,
                QuotaGrant.valid_on == target_day,
            )
        )
        used = await session.scalar(
            select(func.coalesce(func.sum(DailyUsageLedger.units), 0)).where(
                DailyUsageLedger.user_id == user_id,
                DailyUsageLedger.usage_day == target_day,
                DailyUsageLedger.status.in_(("reserved", "charged")),
            )
        )
        limit = (account.daily_run_limit or runtime.base_daily_run_limit) + int(grant_units or 0)
        used_count = int(used or 0)
        return Allowance(
            day=target_day,
            limit=limit,
            used=used_count,
            remaining=max(0, limit - used_count),
            reset_at=next_utc_midnight(target_day),
        )


async def reserve_allowance(
    session: AsyncSession,
    user_id: str,
    run_id: str,
    *,
    auth_session_id: str | None,
    settings: Settings,
    now: datetime,
) -> None:
    # The caller supplies the active SQLAlchemy transaction used to create the run.
    account = await session.scalar(
        select(UserAccount).where(UserAccount.id == user_id).with_for_update()
    )
    if account is None or account.status != "active":
        raise QuotaExceededError
    day = now.date()
    grants = await session.scalar(
        select(func.coalesce(func.sum(QuotaGrant.units), 0)).where(
            QuotaGrant.user_id == user_id,
            QuotaGrant.valid_on == day,
        )
    )
    used = await session.scalar(
        select(func.coalesce(func.sum(DailyUsageLedger.units), 0)).where(
            DailyUsageLedger.user_id == user_id,
            DailyUsageLedger.usage_day == day,
            DailyUsageLedger.status.in_(("reserved", "charged")),
        )
    )
    limit = (account.daily_run_limit or settings.base_daily_run_limit) + int(grants or 0)
    if int(used or 0) >= limit:
        raise QuotaExceededError

    auth_session = (
        await session.get(AuthSession, auth_session_id) if auth_session_id is not None else None
    )
    signal_counters: list[DailySignalUsage] = []
    if auth_session and auth_session.device_digest:
        device_counter = await _locked_signal_usage(
            session, "device", auth_session.device_digest, day, now
        )
        if device_counter.reserved_or_charged_units >= settings.device_daily_run_limit:
            raise QuotaExceededError
        signal_counters.append(device_counter)
    if auth_session and auth_session.ip_pseudonym:
        ip_counter = await _locked_signal_usage(session, "ip", auth_session.ip_pseudonym, day, now)
        if ip_counter.reserved_or_charged_units >= settings.ip_daily_run_limit:
            raise QuotaExceededError
        signal_counters.append(ip_counter)

    dialect_name = session.get_bind().dialect.name
    values = {
        "usage_day": day,
        "reserved_or_charged_units": 0,
        "updated_at": now,
    }
    if dialect_name == "postgresql":
        create_counter = postgresql_insert(DailyServiceUsage).values(**values)
        create_counter = create_counter.on_conflict_do_nothing(index_elements=["usage_day"])
    elif dialect_name == "sqlite":
        create_counter = sqlite_insert(DailyServiceUsage).values(**values)
        create_counter = create_counter.on_conflict_do_nothing(index_elements=["usage_day"])
    else:
        raise RuntimeError(f"Unsupported database dialect: {dialect_name}")
    await session.execute(create_counter)
    service_usage = await session.scalar(
        select(DailyServiceUsage).where(DailyServiceUsage.usage_day == day).with_for_update()
    )
    if service_usage is None:
        raise RuntimeError("Could not initialize daily service usage")
    if service_usage.reserved_or_charged_units >= settings.global_daily_run_limit:
        raise QuotaExceededError

    concurrent = await session.scalar(
        select(func.count(AgentRun.id)).where(
            AgentRun.user_id == user_id,
            AgentRun.status.in_(("accepted", "dispatched", "working")),
        )
    )
    if int(concurrent or 0) >= settings.max_user_concurrent_runs:
        raise ConcurrentRunLimitError
    service_usage.reserved_or_charged_units += 1
    service_usage.updated_at = now
    for counter in signal_counters:
        counter.reserved_or_charged_units += 1
        counter.updated_at = now
    session.add(
        DailyUsageLedger(
            id=str(uuid4()),
            user_id=user_id,
            run_id=run_id,
            device_digest=auth_session.device_digest if auth_session else None,
            ip_pseudonym=auth_session.ip_pseudonym if auth_session else None,
            usage_day=day,
            units=1,
            status="reserved",
            reserved_at=now,
        )
    )


async def charge_allowance(run_id: str) -> None:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        await session.execute(
            update(DailyUsageLedger)
            .where(DailyUsageLedger.run_id == run_id, DailyUsageLedger.status == "reserved")
            .values(status="charged", charged_at=now)
        )


async def release_allowance(run_id: str) -> None:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        await release_reserved_allowance(session, run_id, now=now)


async def release_reserved_allowance(
    session: AsyncSession,
    run_id: str,
    *,
    now: datetime,
) -> bool:
    ledger = await session.scalar(
        select(DailyUsageLedger)
        .where(DailyUsageLedger.run_id == run_id, DailyUsageLedger.status == "reserved")
        .with_for_update()
    )
    if ledger is None:
        return False
    ledger.status = "released"
    ledger.released_at = now
    for signal_type, signal_digest in (
        ("device", ledger.device_digest),
        ("ip", ledger.ip_pseudonym),
    ):
        if signal_digest is None:
            continue
        counter = await session.scalar(
            select(DailySignalUsage)
            .where(
                DailySignalUsage.signal_type == signal_type,
                DailySignalUsage.signal_digest == signal_digest,
                DailySignalUsage.usage_day == ledger.usage_day,
            )
            .with_for_update()
        )
        if counter is not None:
            counter.reserved_or_charged_units = max(
                0, counter.reserved_or_charged_units - ledger.units
            )
            counter.updated_at = now
    service_usage = await session.scalar(
        select(DailyServiceUsage)
        .where(DailyServiceUsage.usage_day == ledger.usage_day)
        .with_for_update()
    )
    if service_usage is not None:
        service_usage.reserved_or_charged_units = max(
            0, service_usage.reserved_or_charged_units - ledger.units
        )
        service_usage.updated_at = now
    return True


async def create_quota_request(
    user_id: str,
    requested_units: int,
    reason: str,
) -> QuotaRequest:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        pending = await session.scalar(
            select(QuotaRequest.id).where(
                QuotaRequest.user_id == user_id,
                QuotaRequest.status == "pending",
            )
        )
        if pending:
            raise ValueError("A quota request is already pending")
        request = QuotaRequest(
            id=str(uuid4()),
            user_id=user_id,
            requested_units=requested_units,
            reason=reason,
            status="pending",
            created_at=now,
        )
        session.add(request)
        await session.flush()
        return request
