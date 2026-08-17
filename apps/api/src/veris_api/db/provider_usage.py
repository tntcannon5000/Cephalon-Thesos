from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select

from veris_api.db.models import AgentRun, ProviderUsage
from veris_api.db.session import get_session_factory


async def record_provider_attempts(
    run_id: str,
    attempts: list[dict[str, Any]],
) -> None:
    if not attempts:
        return
    async with get_session_factory()() as session, session.begin():
        run = await session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None:
            raise RuntimeError(f"Run {run_id} not found")
        current = await session.scalar(
            select(func.max(ProviderUsage.attempt_index)).where(ProviderUsage.run_id == run_id)
        )
        next_index = (current or 0) + 1
        for offset, attempt in enumerate(attempts):
            cost = attempt.get("estimated_cost_usd")
            session.add(
                ProviderUsage(
                    run_id=run_id,
                    attempt_index=next_index + offset,
                    provider=str(attempt.get("provider") or "unknown"),
                    requested_model=str(attempt["requested_model"]),
                    resolved_model=_optional_text(attempt.get("resolved_model")),
                    status=str(attempt["status"]),
                    request_tokens=_optional_int(attempt.get("request_tokens")),
                    response_tokens=_optional_int(attempt.get("response_tokens")),
                    total_tokens=_optional_int(attempt.get("total_tokens")),
                    estimated_cost_usd=Decimal(str(cost)) if cost is not None else None,
                    latency_ms=_optional_int(attempt.get("latency_ms")),
                    cancellation_point=_optional_text(attempt.get("cancellation_point")),
                    error_code=_optional_text(attempt.get("error_code")),
                    provider_request_id=_optional_text(attempt.get("provider_request_id")),
                    metadata_json=dict(attempt.get("metadata_json") or {}),
                    started_at=attempt.get("started_at") or datetime.now(UTC),
                    completed_at=attempt.get("completed_at"),
                    created_at=datetime.now(UTC),
                )
            )


def _optional_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return None


def _optional_text(value: object) -> str | None:
    return str(value) if value is not None else None
