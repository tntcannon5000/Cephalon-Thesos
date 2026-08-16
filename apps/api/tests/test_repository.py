from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from veris_api.db import repository
from veris_api.db.models import AgentEvent, AgentRun, Base


async def test_cancelling_a_run_preserves_latest_snapshot_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cancel.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    now = datetime.now(UTC)
    async with session_factory() as session, session.begin():
        session.add(
            AgentRun(
                id="run-1",
                conversation_id="conversation-1",
                user_message_id="message-1",
                session_id="session-1",
                idempotency_key="idempotency-1",
                status="working",
                model="test-model",
                request_text="Question",
                history_json=[],
                created_at=now,
                updated_at=now,
            )
        )
        session.add_all(
            [
                AgentEvent(
                    run_id="run-1",
                    sequence=1,
                    event_type="run.accepted",
                    payload={},
                    created_at=now,
                ),
                AgentEvent(
                    run_id="run-1",
                    sequence=2,
                    event_type="answer.snapshot",
                    payload={"text": "A partial response"},
                    created_at=now,
                ),
            ]
        )

    monkeypatch.setattr(repository, "get_session_factory", lambda: session_factory)

    assert await repository.mark_run_cancelled("run-1") is True
    assert await repository.mark_run_cancelled("run-1") is False

    async with session_factory() as session:
        run = await session.get(AgentRun, "run-1")
        cancelled_events = list(
            await session.scalars(
                select(AgentEvent).where(AgentEvent.event_type == "run.cancelled")
            )
        )

    assert run is not None
    assert run.status == "cancelled"
    assert run.answer_text == "A partial response"
    assert len(cancelled_events) == 1
    assert cancelled_events[0].payload == {"partial_answer": "A partial response"}
    await engine.dispose()
