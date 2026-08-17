from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from veris_api.db import dispatch, repository, retention
from veris_api.db.models import AgentEvent, AgentRun
from veris_api.schemas import CreateRunRequest

POSTGRES_URL = os.getenv("THESOS_INTEGRATION_DATABASE_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="PostgreSQL integration URL not set")


async def test_postgres_idempotency_event_allocation_dispatch_and_purge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert POSTGRES_URL is not None
    engine = create_async_engine(POSTGRES_URL, pool_size=6, max_overflow=2)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE provider_usage, agent_event, conversation_message_control, "
                "agent_run, runtime_worker CASCADE"
            )
        )

    runtime_settings = SimpleNamespace(
        openrouter_model="test/model",
        openrouter_fallback_models=(),
        run_retention_days=30,
        worker_max_dispatch_attempts=3,
        worker_lease_seconds=60,
    )
    monkeypatch.setattr(repository, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(repository, "get_settings", lambda: runtime_settings)
    monkeypatch.setattr(dispatch, "get_session_factory", lambda: session_factory)
    monkeypatch.setattr(dispatch, "get_settings", lambda: runtime_settings)
    monkeypatch.setattr(retention, "get_session_factory", lambda: session_factory)

    conversation_id = str(uuid4())
    message_id = str(uuid4())
    request = CreateRunRequest(
        message="How does multishot work?",
        conversation_id=conversation_id,
        message_id=message_id,
    )
    first, retry = await asyncio.gather(
        repository.create_run(request, session_id="session-a", idempotency_key="idem-key-a"),
        repository.create_run(request, session_id="session-a", idempotency_key="idem-key-a"),
    )
    assert first.run_id == retry.run_id
    assert sorted((first.created, retry.created)) == [False, True]

    await asyncio.gather(
        *(
            repository.add_event(first.run_id, "test.concurrent", {"index": index})
            for index in range(12)
        )
    )
    async with session_factory() as session:
        sequences = list(
            await session.scalars(
                select(AgentEvent.sequence)
                .where(AgentEvent.run_id == first.run_id)
                .order_by(AgentEvent.sequence)
            )
        )
    assert sequences == list(range(1, 14))

    claimed = await asyncio.gather(
        dispatch.claim_next_run("worker-a"),
        dispatch.claim_next_run("worker-b"),
    )
    assert sum(item is not None for item in claimed) == 1
    owner = next(item for item in claimed if item is not None)
    assert owner.run_id == first.run_id

    expired_at = datetime.now(UTC) - timedelta(minutes=1)
    async with session_factory() as session, session.begin():
        await session.execute(
            update(AgentRun)
            .where(AgentRun.id == first.run_id)
            .values(status="completed", expires_at=expired_at)
        )
    assert await retention.purge_expired_runs() == [first.run_id]
    async with session_factory() as session:
        assert await session.get(AgentRun, first.run_id) is None
        assert (
            await session.scalar(
                select(AgentEvent.id).where(AgentEvent.run_id == first.run_id).limit(1)
            )
            is None
        )
    await engine.dispose()
