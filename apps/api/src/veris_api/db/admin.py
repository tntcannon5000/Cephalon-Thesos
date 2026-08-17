from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import distinct, func, select, text, update
from sqlalchemy.sql.elements import ColumnElement

from veris_api.db.models import (
    AccessAllowlist,
    AccessRequest,
    AgentRun,
    AuditEvent,
    AuthSession,
    DailyUsageLedger,
    ProviderUsage,
    QuotaGrant,
    QuotaRequest,
    RuntimeWorker,
    UserAccount,
    UserRole,
)
from veris_api.db.session import get_session_factory


@dataclass(frozen=True)
class MetricsWindow:
    start: datetime
    end: datetime
    bucket_starts: tuple[datetime, ...]
    bucket_expression: ColumnElement[Any]


def _shift_month(value: datetime, months: int) -> datetime:
    position = value.year * 12 + value.month - 1 + months
    return value.replace(year=position // 12, month=position % 12 + 1, day=1)


def metrics_window(period: str, *, now: datetime | None = None) -> MetricsWindow:
    current = (now or datetime.now(UTC)).astimezone(UTC)
    if period == "year":
        final_month = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start = _shift_month(final_month, -11)
        end = _shift_month(final_month, 1)
        starts = tuple(_shift_month(start, index) for index in range(12))
        return MetricsWindow(start, end, starts, func.date_trunc("month", ProviderUsage.created_at))

    definitions = {
        "15m": (timedelta(minutes=1), 15),
        "hour": (timedelta(minutes=5), 12),
        "day": (timedelta(hours=1), 24),
        "week": (timedelta(days=1), 7),
        "month": (timedelta(days=1), 30),
    }
    bucket, count = definitions[period]
    seconds = int(bucket.total_seconds())
    epoch_seconds = int(current.timestamp())
    end = datetime.fromtimestamp((epoch_seconds // seconds + 1) * seconds, tz=UTC)
    start = end - bucket * count
    starts = tuple(start + bucket * index for index in range(count))
    expression = func.date_bin(
        text(f"INTERVAL '{seconds} seconds'"),
        ProviderUsage.created_at,
        datetime(1970, 1, 1, tzinfo=UTC),
    )
    return MetricsWindow(start, end, starts, expression)


async def usage_metrics(period: str) -> dict[str, object]:
    window = metrics_window(period)
    bucket = window.bucket_expression
    model_name = func.coalesce(ProviderUsage.resolved_model, ProviderUsage.requested_model)
    async with get_session_factory()() as session:
        timeline_rows = (
            await session.execute(
                select(
                    bucket.label("bucket"),
                    func.count(ProviderUsage.id),
                    func.count(distinct(ProviderUsage.run_id)),
                    func.coalesce(func.sum(ProviderUsage.request_tokens), 0),
                    func.coalesce(func.sum(ProviderUsage.response_tokens), 0),
                    func.coalesce(func.sum(ProviderUsage.total_tokens), 0),
                    func.coalesce(func.sum(ProviderUsage.estimated_cost_usd), Decimal("0")),
                )
                .where(
                    ProviderUsage.created_at >= window.start,
                    ProviderUsage.created_at < window.end,
                )
                .group_by(bucket)
                .order_by(bucket)
            )
        ).all()
        user_rows = (
            await session.execute(
                select(
                    UserAccount.id,
                    UserAccount.email,
                    func.count(distinct(ProviderUsage.run_id)),
                    func.coalesce(func.sum(ProviderUsage.total_tokens), 0),
                    func.coalesce(func.sum(ProviderUsage.estimated_cost_usd), Decimal("0")),
                )
                .join(AgentRun, AgentRun.user_id == UserAccount.id)
                .join(ProviderUsage, ProviderUsage.run_id == AgentRun.id)
                .where(
                    ProviderUsage.created_at >= window.start,
                    ProviderUsage.created_at < window.end,
                )
                .group_by(UserAccount.id, UserAccount.email)
                .order_by(func.sum(ProviderUsage.total_tokens).desc())
            )
        ).all()
        model_rows = (
            await session.execute(
                select(
                    ProviderUsage.provider,
                    model_name.label("model"),
                    func.count(ProviderUsage.id),
                    func.coalesce(func.sum(ProviderUsage.total_tokens), 0),
                    func.coalesce(func.sum(ProviderUsage.estimated_cost_usd), Decimal("0")),
                    func.avg(ProviderUsage.latency_ms),
                )
                .where(
                    ProviderUsage.created_at >= window.start,
                    ProviderUsage.created_at < window.end,
                )
                .group_by(ProviderUsage.provider, model_name)
                .order_by(func.sum(ProviderUsage.total_tokens).desc())
            )
        ).all()

    rows_by_bucket = {row[0].astimezone(UTC): row for row in timeline_rows}
    points = []
    for started_at in window.bucket_starts:
        row = rows_by_bucket.get(started_at)
        points.append(
            {
                "started_at": started_at,
                "attempts": int(row[1] if row else 0),
                "runs": int(row[2] if row else 0),
                "request_tokens": int(row[3] if row else 0),
                "response_tokens": int(row[4] if row else 0),
                "total_tokens": int(row[5] if row else 0),
                "estimated_cost_usd": str(row[6] if row else Decimal("0")),
            }
        )
    return {
        "period": period,
        "starts_at": window.start,
        "ends_at": window.end,
        "attempts": sum(point["attempts"] for point in points),
        "runs": sum(point["runs"] for point in points),
        "request_tokens": sum(point["request_tokens"] for point in points),
        "response_tokens": sum(point["response_tokens"] for point in points),
        "total_tokens": sum(point["total_tokens"] for point in points),
        "estimated_cost_usd": str(
            sum((Decimal(point["estimated_cost_usd"]) for point in points), Decimal("0"))
        ),
        "points": points,
        "users": [
            {
                "user_id": row[0],
                "email": row[1],
                "runs": int(row[2]),
                "total_tokens": int(row[3]),
                "estimated_cost_usd": str(row[4]),
            }
            for row in user_rows
        ],
        "models": [
            {
                "provider": row[0],
                "model": row[1],
                "attempts": int(row[2]),
                "total_tokens": int(row[3]),
                "estimated_cost_usd": str(row[4]),
                "average_latency_ms": int(row[5]) if row[5] is not None else None,
            }
            for row in model_rows
        ],
    }


async def overview() -> dict[str, int | str]:
    today = datetime.now(UTC).date()
    worker_cutoff = datetime.now(UTC) - timedelta(seconds=15)
    async with get_session_factory()() as session:
        users = await session.scalar(select(func.count(UserAccount.id)))
        active_users = await session.scalar(
            select(func.count(UserAccount.id)).where(UserAccount.status == "active")
        )
        pending_access = await session.scalar(
            select(func.count(AccessRequest.id)).where(AccessRequest.status == "pending")
        )
        pending_quota = await session.scalar(
            select(func.count(QuotaRequest.id)).where(QuotaRequest.status == "pending")
        )
        runs_today = await session.scalar(
            select(func.count(distinct(DailyUsageLedger.run_id))).where(
                DailyUsageLedger.usage_day == today,
                DailyUsageLedger.status == "charged",
            )
        )
        usage = (
            await session.execute(
                select(
                    func.coalesce(func.sum(ProviderUsage.total_tokens), 0),
                    func.coalesce(func.sum(ProviderUsage.estimated_cost_usd), Decimal("0")),
                ).where(func.date(ProviderUsage.created_at) == today)
            )
        ).one()
        active_runs = await session.scalar(
            select(func.count(AgentRun.id)).where(
                AgentRun.status.in_(("accepted", "dispatched", "working"))
            )
        )
        live_workers = await session.scalar(
            select(func.count(RuntimeWorker.id)).where(
                RuntimeWorker.last_heartbeat_at >= worker_cutoff
            )
        )
        return {
            "users": int(users or 0),
            "active_users": int(active_users or 0),
            "pending_access_requests": int(pending_access or 0),
            "pending_quota_requests": int(pending_quota or 0),
            "runs_today": int(runs_today or 0),
            "tokens_today": int(usage[0] or 0),
            "estimated_cost_usd_today": str(usage[1] or Decimal("0")),
            "active_runs": int(active_runs or 0),
            "live_workers": int(live_workers or 0),
        }


async def list_users() -> list[dict[str, object]]:
    today = datetime.now(UTC).date()
    async with get_session_factory()() as session:
        accounts = list(await session.scalars(select(UserAccount).order_by(UserAccount.created_at)))
        result: list[dict[str, object]] = []
        for account in accounts:
            roles = list(
                await session.scalars(select(UserRole.role).where(UserRole.user_id == account.id))
            )
            runs = await session.scalar(
                select(func.coalesce(func.sum(DailyUsageLedger.units), 0)).where(
                    DailyUsageLedger.user_id == account.id,
                    DailyUsageLedger.usage_day == today,
                    DailyUsageLedger.status.in_(("reserved", "charged")),
                )
            )
            result.append(
                {
                    "id": account.id,
                    "email": account.email,
                    "status": account.status,
                    "roles": roles,
                    "daily_run_limit": account.daily_run_limit,
                    "runs_today": int(runs or 0),
                    "created_at": account.created_at,
                }
            )
        return result


async def add_allowlist_entry(
    email: str,
    *,
    role: str | None,
    actor_user_id: str,
) -> AccessAllowlist:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        account = await session.scalar(
            select(UserAccount).where(UserAccount.email == email).with_for_update()
        )
        existing = await session.scalar(
            select(AccessAllowlist).where(AccessAllowlist.email == email).with_for_update()
        )
        if existing:
            existing.status = "active"
            if role:
                existing.role_on_registration = role
            existing.updated_at = now
            entry = existing
        else:
            entry = AccessAllowlist(
                id=str(uuid4()),
                email=email,
                status="active",
                role_on_registration=role,
                created_by_user_id=actor_user_id,
                created_at=now,
                updated_at=now,
            )
            session.add(entry)
            await session.flush()
        if role == "admin" and account is not None:
            assigned = await session.get(UserRole, (account.id, "admin"))
            if assigned is None:
                session.add(
                    UserRole(
                        user_id=account.id,
                        role="admin",
                        granted_by_user_id=actor_user_id,
                        granted_at=now,
                    )
                )
        return entry


async def list_access_requests() -> list[AccessRequest]:
    async with get_session_factory()() as session:
        return list(
            await session.scalars(
                select(AccessRequest).order_by(AccessRequest.status, AccessRequest.created_at)
            )
        )


async def resolve_access_request(
    request_id: str,
    resolution: str,
    *,
    actor_user_id: str,
) -> AccessRequest | None:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        access_request = await session.get(AccessRequest, request_id, with_for_update=True)
        if access_request is None or access_request.status != "pending":
            return None
        access_request.status = resolution
        access_request.resolved_by_user_id = actor_user_id
        access_request.resolved_at = now
        if resolution == "approved":
            entry = await session.scalar(
                select(AccessAllowlist)
                .where(AccessAllowlist.email == access_request.email)
                .with_for_update()
            )
            if entry:
                entry.status = "active"
                entry.updated_at = now
            else:
                session.add(
                    AccessAllowlist(
                        id=str(uuid4()),
                        email=access_request.email,
                        status="active",
                        created_by_user_id=actor_user_id,
                        created_at=now,
                        updated_at=now,
                    )
                )
        return access_request


async def update_user_status(
    user_id: str,
    status: str,
    *,
    actor_user_id: str,
) -> bool:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        account = await session.get(UserAccount, user_id, with_for_update=True)
        if account is None or user_id == actor_user_id:
            return False
        if status == "active" and account.email_verified_at is None:
            return False
        account.status = status
        account.updated_at = now
        if status != "active":
            await session.execute(
                update(AuthSession)
                .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=now, revoke_reason=f"account_{status}")
            )
        return True


async def create_grant(
    user_id: str,
    units: int,
    valid_on: date,
    reason: str | None,
    *,
    actor_user_id: str,
) -> QuotaGrant:
    grant = QuotaGrant(
        id=str(uuid4()),
        user_id=user_id,
        valid_on=valid_on,
        units=units,
        reason=reason,
        created_by_user_id=actor_user_id,
        created_at=datetime.now(UTC),
    )
    async with get_session_factory()() as session, session.begin():
        if await session.get(UserAccount, user_id) is None:
            raise ValueError("Account not found")
        session.add(grant)
        await session.flush()
        return grant


async def list_quota_requests() -> list[dict[str, object]]:
    async with get_session_factory()() as session:
        rows = await session.execute(
            select(QuotaRequest, UserAccount.email)
            .join(UserAccount, UserAccount.id == QuotaRequest.user_id)
            .order_by(QuotaRequest.status, QuotaRequest.created_at)
        )
        return [
            {
                "id": request.id,
                "user_id": request.user_id,
                "email": email,
                "requested_units": request.requested_units,
                "reason": request.reason,
                "status": request.status,
                "created_at": request.created_at,
            }
            for request, email in rows
        ]


async def resolve_quota_request(
    request_id: str,
    resolution: str,
    grant_units: int | None,
    *,
    actor_user_id: str,
) -> QuotaRequest | None:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        request = await session.get(QuotaRequest, request_id, with_for_update=True)
        if request is None or request.status != "pending":
            return None
        request.status = resolution
        request.resolved_by_user_id = actor_user_id
        request.resolved_at = now
        if resolution == "approved":
            session.add(
                QuotaGrant(
                    id=str(uuid4()),
                    user_id=request.user_id,
                    valid_on=now.date(),
                    units=grant_units or request.requested_units,
                    reason="Approved quota request",
                    created_by_user_id=actor_user_id,
                    created_at=now,
                )
            )
        return request


async def list_audit_events(limit: int = 100) -> list[AuditEvent]:
    async with get_session_factory()() as session:
        return list(
            await session.scalars(
                select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)
            )
        )


async def list_user_sessions(user_id: str) -> list[dict[str, object]]:
    async with get_session_factory()() as session:
        sessions = list(
            await session.scalars(
                select(AuthSession)
                .where(AuthSession.user_id == user_id)
                .order_by(AuthSession.created_at.desc())
            )
        )
        return [
            {
                "id": item.id,
                "created_at": item.created_at,
                "last_seen_at": item.last_seen_at,
                "absolute_expires_at": item.absolute_expires_at,
                "revoked_at": item.revoked_at,
                "revoke_reason": item.revoke_reason,
            }
            for item in sessions
        ]


async def revoke_managed_session(session_id: str, actor_user_id: str) -> bool:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        managed = await session.get(AuthSession, session_id, with_for_update=True)
        if managed is None or managed.user_id == actor_user_id:
            return False
        managed.revoked_at = managed.revoked_at or now
        managed.revoke_reason = managed.revoke_reason or "admin_revoked"
        return True


async def recent_failures(limit: int = 50) -> list[dict[str, object]]:
    async with get_session_factory()() as session:
        runs = list(
            await session.scalars(
                select(AgentRun)
                .where(AgentRun.status == "failed")
                .order_by(AgentRun.updated_at.desc())
                .limit(limit)
            )
        )
        return [
            {
                "run_id": run.id,
                "user_id": run.user_id,
                "model": run.model,
                "error_code": run.error_code,
                "created_at": run.created_at,
                "updated_at": run.updated_at,
            }
            for run in runs
        ]
