from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError

from veris_api.config import get_settings
from veris_api.db.models import AgentEvent, AgentRun, MessageControl
from veris_api.db.session import get_session_factory
from veris_api.schemas import ConversationMessage, CreateRunRequest


class ConversationTerminatedError(Exception):
    pass


class MessageNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class CreatedRun:
    run_id: str
    created: bool


def hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def create_run(
    request: CreateRunRequest,
    *,
    session_id: str,
    idempotency_key: str,
) -> CreatedRun:
    settings = get_settings()
    model_route = (settings.openrouter_model, *settings.openrouter_fallback_models)
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        existing = await session.scalar(
            select(AgentRun.id).where(
                AgentRun.session_id == session_id,
                AgentRun.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return CreatedRun(existing, created=False)

        terminated = await session.scalar(
            select(MessageControl.id).where(
                MessageControl.conversation_id == request.conversation_id,
                MessageControl.session_id == session_id,
                MessageControl.active.is_(True),
                MessageControl.safety_action == "terminate_conversation",
            )
        )
        if terminated:
            raise ConversationTerminatedError

        max_ordinal = await session.scalar(
            select(func.max(MessageControl.ordinal)).where(
                MessageControl.conversation_id == request.conversation_id,
                MessageControl.active.is_(True),
            )
        )
        ordinal = (max_ordinal or 0) + 1
        now = datetime.now(UTC)
        run_id = str(uuid4())

        session.add(
            MessageControl(
                id=request.message_id,
                conversation_id=request.conversation_id,
                session_id=session_id,
                ordinal=ordinal,
                role="user",
                content_hash=hash_content(request.message),
                safety_action="pending",
                active=True,
                created_at=now,
            )
        )
        session.add(
            AgentRun(
                id=run_id,
                conversation_id=request.conversation_id,
                user_message_id=request.message_id,
                session_id=session_id,
                idempotency_key=idempotency_key,
                status="accepted",
                model=settings.openrouter_model,
                request_text=request.message,
                user_display_name=request.display_name,
                history_json=[message.model_dump() for message in request.history],
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            AgentEvent(
                run_id=run_id,
                sequence=1,
                event_type="run.accepted",
                payload={"mode": request.mode, "model_route": model_route},
                created_at=now,
            )
        )
        try:
            await session.flush()
        except IntegrityError:
            await session.rollback()
            async with session_factory() as retry_session:
                existing = await retry_session.scalar(
                    select(AgentRun.id).where(
                        AgentRun.session_id == session_id,
                        AgentRun.idempotency_key == idempotency_key,
                    )
                )
                if existing:
                    return CreatedRun(existing, created=False)
            raise
        return CreatedRun(run_id, created=True)


async def get_run_for_session(run_id: str, session_id: str) -> AgentRun | None:
    async with get_session_factory()() as session:
        return await session.scalar(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.session_id == session_id)
        )


async def get_run(run_id: str) -> AgentRun | None:
    async with get_session_factory()() as session:
        return await session.get(AgentRun, run_id)


async def add_event(run_id: str, event_type: str, payload: dict[str, Any]) -> int:
    async with get_session_factory()() as session, session.begin():
        current = await session.scalar(
            select(func.max(AgentEvent.sequence)).where(AgentEvent.run_id == run_id)
        )
        sequence = (current or 0) + 1
        session.add(
            AgentEvent(
                run_id=run_id,
                sequence=sequence,
                event_type=event_type,
                payload=payload,
                created_at=datetime.now(UTC),
            )
        )
        return sequence


async def events_after(run_id: str, sequence: int) -> list[AgentEvent]:
    async with get_session_factory()() as session:
        events = await session.scalars(
            select(AgentEvent)
            .where(AgentEvent.run_id == run_id, AgentEvent.sequence > sequence)
            .order_by(AgentEvent.sequence)
        )
        return list(events)


async def set_run_status(
    run_id: str,
    status: str,
    *,
    answer: str | None = None,
    error_code: str | None = None,
) -> None:
    values: dict[str, Any] = {
        "status": status,
        "updated_at": datetime.now(UTC),
    }
    if answer is not None:
        values["answer_text"] = answer
    if error_code is not None:
        values["error_code"] = error_code
    async with get_session_factory()() as session, session.begin():
        await session.execute(update(AgentRun).where(AgentRun.id == run_id).values(**values))


async def set_message_safety(message_id: str, safety_action: str) -> None:
    async with get_session_factory()() as session, session.begin():
        await session.execute(
            update(MessageControl)
            .where(MessageControl.id == message_id)
            .values(safety_action=safety_action)
        )


async def edit_message(
    conversation_id: str,
    message_id: str,
    *,
    session_id: str,
) -> list[str]:
    async with get_session_factory()() as session, session.begin():
        target = await session.scalar(
            select(MessageControl).where(
                MessageControl.id == message_id,
                MessageControl.conversation_id == conversation_id,
                MessageControl.session_id == session_id,
                MessageControl.active.is_(True),
            )
        )
        if target is None:
            raise MessageNotFoundError

        removed = await session.scalars(
            select(MessageControl.id).where(
                MessageControl.conversation_id == conversation_id,
                MessageControl.session_id == session_id,
                MessageControl.active.is_(True),
                MessageControl.ordinal >= target.ordinal,
            )
        )
        removed_ids = list(removed)
        await session.execute(
            delete(MessageControl).where(
                MessageControl.conversation_id == conversation_id,
                MessageControl.session_id == session_id,
                MessageControl.ordinal >= target.ordinal,
            )
        )
        return removed_ids


def format_history(history: list[dict[str, str]] | list[ConversationMessage]) -> str:
    lines: list[str] = []
    for message in history[-12:]:
        role = message["role"] if isinstance(message, dict) else message.role
        content = message["content"] if isinstance(message, dict) else message.content
        lines.append(f"{role.upper()}: {content}")
    return "\n\n".join(lines)
