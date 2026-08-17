from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from veris_api.config import get_settings
from veris_api.db.models import (
    AgentEvent,
    AgentRun,
    ConversationMessageRecord,
    ConversationRecord,
    MessageControl,
)
from veris_api.db.quota import release_reserved_allowance, reserve_allowance
from veris_api.db.session import get_session_factory
from veris_api.schemas import ConversationMessage, CreateRunRequest

TERMINAL_RUN_STATUSES = {"completed", "failed", "cancelled", "terminated"}


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
    user_id: str | None = None,
    auth_session_id: str | None = None,
) -> CreatedRun:
    settings = get_settings()
    model_route = (settings.openrouter_model, *settings.openrouter_fallback_models)
    session_factory = get_session_factory()
    async with session_factory() as session, session.begin():
        ownership_filter = (
            AgentRun.user_id == user_id
            if user_id is not None
            else AgentRun.session_id == session_id
        )
        existing = await session.scalar(
            select(AgentRun.id).where(
                ownership_filter,
                AgentRun.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return CreatedRun(existing, created=False)

        message_owner_filter = (
            MessageControl.user_id == user_id
            if user_id is not None
            else MessageControl.session_id == session_id
        )
        terminated = await session.scalar(
            select(MessageControl.id).where(
                MessageControl.conversation_id == request.conversation_id,
                message_owner_filter,
                MessageControl.active.is_(True),
                MessageControl.safety_action == "terminate_conversation",
            )
        )
        if terminated:
            raise ConversationTerminatedError

        max_ordinal = await session.scalar(
            select(func.max(MessageControl.ordinal)).where(
                MessageControl.conversation_id == request.conversation_id,
                message_owner_filter,
                MessageControl.active.is_(True),
            )
        )
        ordinal = (max_ordinal or 0) + 1
        now = datetime.now(UTC)
        run_id = str(uuid4())

        history_json = [message.model_dump() for message in request.history]
        if user_id is not None:
            conversation = await session.get(
                ConversationRecord,
                request.conversation_id,
                with_for_update=True,
            )
            if conversation is not None and conversation.user_id != user_id:
                raise MessageNotFoundError
            if conversation is None:
                conversation = ConversationRecord(
                    id=request.conversation_id,
                    user_id=user_id,
                    title=request.message[:80],
                    title_state="pending",
                    pinned=False,
                    terminated=False,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
                session.add(conversation)
                await session.flush()
                for index, message in enumerate(request.history, start=1):
                    session.add(
                        ConversationMessageRecord(
                            id=message.id,
                            conversation_id=request.conversation_id,
                            user_id=user_id,
                            ordinal=index,
                            role=message.role,
                            content=message.content,
                            state="complete",
                            created_at=now,
                        )
                    )
            else:
                persisted_messages = list(
                    await session.scalars(
                        select(ConversationMessageRecord)
                        .where(ConversationMessageRecord.conversation_id == request.conversation_id)
                        .order_by(ConversationMessageRecord.ordinal)
                    )
                )
                persisted_current = next(
                    (item for item in persisted_messages if item.id == request.message_id),
                    None,
                )
                if persisted_current is not None and (
                    persisted_current.role != "user" or persisted_current.content != request.message
                ):
                    raise MessageNotFoundError
                history_json = [
                    {"id": item.id, "role": item.role, "content": item.content}
                    for item in persisted_messages
                    if item.id != request.message_id
                ]
                history_json = history_json[-20:]
            next_message_ordinal = (
                await session.scalar(
                    select(func.max(ConversationMessageRecord.ordinal)).where(
                        ConversationMessageRecord.conversation_id == request.conversation_id
                    )
                )
                or 0
            ) + 1
            if conversation is not None and not await session.get(
                ConversationMessageRecord, request.message_id
            ):
                session.add(
                    ConversationMessageRecord(
                        id=request.message_id,
                        conversation_id=request.conversation_id,
                        user_id=user_id,
                        ordinal=next_message_ordinal,
                        role="user",
                        content=request.message,
                        state="complete",
                        created_at=now,
                    )
                )
            conversation.updated_at = now
            conversation.revision += 1
            await reserve_allowance(
                session,
                user_id,
                run_id,
                auth_session_id=auth_session_id,
                settings=settings,
                now=now,
            )

        session.add(
            MessageControl(
                id=request.message_id,
                conversation_id=request.conversation_id,
                session_id=session_id,
                user_id=user_id,
                auth_session_id=auth_session_id,
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
                user_id=user_id,
                auth_session_id=auth_session_id,
                idempotency_key=idempotency_key,
                status="accepted",
                model=settings.openrouter_model,
                request_text=request.message,
                user_display_name=request.display_name,
                history_json=history_json,
                last_event_sequence=1,
                dispatch_attempts=0,
                next_attempt_at=now,
                expires_at=now + timedelta(days=settings.run_retention_days),
                created_at=now,
                updated_at=now,
            )
        )
        try:
            # Flush the parent row before the event. SQLite's disabled-by-default
            # foreign keys hid this ordering requirement during the local prototype.
            await session.flush()
            session.add(
                AgentEvent(
                    run_id=run_id,
                    sequence=1,
                    event_type="run.accepted",
                    payload={"mode": request.mode, "model_route": model_route},
                    created_at=now,
                )
            )
            await session.flush()
        except IntegrityError:
            await session.rollback()
            async with session_factory() as retry_session:
                existing = await retry_session.scalar(
                    select(AgentRun.id).where(
                        ownership_filter,
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


async def get_run_for_user(run_id: str, user_id: str) -> AgentRun | None:
    async with get_session_factory()() as session:
        return await session.scalar(
            select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
        )


async def get_run(run_id: str) -> AgentRun | None:
    async with get_session_factory()() as session:
        return await session.get(AgentRun, run_id)


async def add_event(run_id: str, event_type: str, payload: dict[str, Any]) -> int:
    async with get_session_factory()() as session, session.begin():
        run = await session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None:
            raise RuntimeError(f"Run {run_id} not found")
        sequence = await _allocate_event_sequence(session, run)
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


async def _allocate_event_sequence(session: AsyncSession, run: AgentRun) -> int:
    persisted_max = await session.scalar(
        select(func.max(AgentEvent.sequence)).where(AgentEvent.run_id == run.id)
    )
    run.last_event_sequence = max(run.last_event_sequence, persisted_max or 0) + 1
    return run.last_event_sequence


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
) -> bool:
    async with get_session_factory()() as session, session.begin():
        run = await session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if (
            run is None
            or run.status in TERMINAL_RUN_STATUSES
            or (status == "working" and run.cancel_requested_at is not None)
        ):
            return False
        run.status = status
        run.updated_at = datetime.now(UTC)
        if answer is not None:
            run.answer_text = answer
        if error_code is not None:
            run.error_code = error_code
        if status in TERMINAL_RUN_STATUSES:
            run.lease_owner = None
            run.lease_expires_at = None
        return True


async def finalize_run(
    run_id: str,
    status: str,
    events: list[tuple[str, dict[str, Any]]],
    *,
    message_id: str | None = None,
    safety_action: str | None = None,
    answer: str | None = None,
    error_code: str | None = None,
) -> bool:
    if status not in TERMINAL_RUN_STATUSES:
        raise ValueError(f"Unsupported terminal status: {status}")
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        run = await session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None or run.status in TERMINAL_RUN_STATUSES:
            return False
        run.status = status
        run.updated_at = now
        run.lease_owner = None
        run.lease_expires_at = None
        if answer is not None:
            run.answer_text = answer
        if error_code is not None:
            run.error_code = error_code
        await _persist_conversation_result(session, run, status, events, answer, now)
        if message_id is not None and safety_action is not None:
            await session.execute(
                update(MessageControl)
                .where(MessageControl.id == message_id)
                .values(safety_action=safety_action)
            )
        for event_type, payload in events:
            sequence = await _allocate_event_sequence(session, run)
            session.add(
                AgentEvent(
                    run_id=run_id,
                    sequence=sequence,
                    event_type=event_type,
                    payload=payload,
                    created_at=now,
                )
            )
        return True


async def mark_run_cancelled(run_id: str) -> bool:
    async with get_session_factory()() as session, session.begin():
        run = await session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None or run.status in TERMINAL_RUN_STATUSES:
            return False

        latest_snapshot = await session.scalar(
            select(AgentEvent)
            .where(
                AgentEvent.run_id == run_id,
                AgentEvent.event_type == "answer.snapshot",
            )
            .order_by(AgentEvent.sequence.desc())
            .limit(1)
        )
        partial_answer = latest_snapshot.payload.get("text") if latest_snapshot else None
        run.status = "cancelled"
        run.updated_at = datetime.now(UTC)
        run.cancel_requested_at = run.cancel_requested_at or datetime.now(UTC)
        run.lease_owner = None
        run.lease_expires_at = None
        if isinstance(partial_answer, str) and partial_answer:
            run.answer_text = partial_answer
            await _persist_conversation_result(
                session,
                run,
                "cancelled",
                [],
                partial_answer,
                datetime.now(UTC),
            )

        sequence = await _allocate_event_sequence(session, run)
        session.add(
            AgentEvent(
                run_id=run_id,
                sequence=sequence,
                event_type="run.cancelled",
                payload={"partial_answer": partial_answer or ""},
                created_at=datetime.now(UTC),
            )
        )
        return True


async def request_run_cancellation(run_id: str) -> bool:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        run = await session.scalar(select(AgentRun).where(AgentRun.id == run_id).with_for_update())
        if run is None or run.status in TERMINAL_RUN_STATUSES:
            return False
        if run.cancel_requested_at is not None:
            return True

        run.cancel_requested_at = now
        run.updated_at = now
        if run.status == "accepted":
            run.status = "cancelled"
            await release_reserved_allowance(session, run_id, now=now)
            sequence = await _allocate_event_sequence(session, run)
            session.add(
                AgentEvent(
                    run_id=run.id,
                    sequence=sequence,
                    event_type="run.cancelled",
                    payload={"partial_answer": ""},
                    created_at=now,
                )
            )
        else:
            sequence = await _allocate_event_sequence(session, run)
            session.add(
                AgentEvent(
                    run_id=run.id,
                    sequence=sequence,
                    event_type="status.changed",
                    payload={"kind": "stopping", "label": "Stopping"},
                    created_at=now,
                )
            )
        return True


async def _persist_conversation_result(
    session: AsyncSession,
    run: AgentRun,
    status: str,
    events: list[tuple[str, dict[str, Any]]],
    answer: str | None,
    now: datetime,
) -> None:
    if run.user_id is None:
        return
    conversation = await session.scalar(
        select(ConversationRecord)
        .where(
            ConversationRecord.id == run.conversation_id,
            ConversationRecord.user_id == run.user_id,
        )
        .with_for_update()
    )
    if conversation is None:
        return
    if status == "terminated":
        conversation.terminated = True
    for event_type, payload in events:
        if event_type == "conversation.titled" and isinstance(payload.get("title"), str):
            conversation.title = str(payload["title"])[:80]
            conversation.title_state = "generated"
    if answer:
        assistant_id = f"v-{run.user_message_id}"
        message = await session.get(ConversationMessageRecord, assistant_id)
        if message is None:
            ordinal = (
                await session.scalar(
                    select(func.max(ConversationMessageRecord.ordinal)).where(
                        ConversationMessageRecord.conversation_id == run.conversation_id
                    )
                )
                or 0
            ) + 1
            session.add(
                ConversationMessageRecord(
                    id=assistant_id,
                    conversation_id=run.conversation_id,
                    user_id=run.user_id,
                    ordinal=ordinal,
                    role="assistant",
                    content=answer,
                    state="complete",
                    created_at=now,
                )
            )
        else:
            message.content = answer
            message.state = "complete"
    conversation.updated_at = now
    conversation.revision += 1


async def edit_message(
    conversation_id: str,
    message_id: str,
    *,
    session_id: str,
    user_id: str | None = None,
) -> list[str]:
    async with get_session_factory()() as session, session.begin():
        owner_filter = (
            MessageControl.user_id == user_id
            if user_id is not None
            else MessageControl.session_id == session_id
        )
        target = await session.scalar(
            select(MessageControl).where(
                MessageControl.id == message_id,
                MessageControl.conversation_id == conversation_id,
                owner_filter,
                MessageControl.active.is_(True),
            )
        )
        if target is None:
            raise MessageNotFoundError

        removed = await session.scalars(
            select(MessageControl.id).where(
                MessageControl.conversation_id == conversation_id,
                owner_filter,
                MessageControl.active.is_(True),
                MessageControl.ordinal >= target.ordinal,
            )
        )
        removed_ids = list(removed)
        await session.execute(
            delete(MessageControl).where(
                MessageControl.conversation_id == conversation_id,
                owner_filter,
                MessageControl.ordinal >= target.ordinal,
            )
        )
        if user_id is not None:
            conversation_message = await session.get(
                ConversationMessageRecord,
                message_id,
            )
            if conversation_message and conversation_message.user_id == user_id:
                await session.execute(
                    delete(ConversationMessageRecord).where(
                        ConversationMessageRecord.conversation_id == conversation_id,
                        ConversationMessageRecord.user_id == user_id,
                        ConversationMessageRecord.ordinal >= conversation_message.ordinal,
                    )
                )
                conversation = await session.get(ConversationRecord, conversation_id)
                if conversation:
                    conversation.terminated = False
                    conversation.updated_at = datetime.now(UTC)
                    conversation.revision += 1
        return removed_ids


def format_history(history: list[dict[str, str]] | list[ConversationMessage]) -> str:
    lines: list[str] = []
    for message in history[-12:]:
        role = message["role"] if isinstance(message, dict) else message.role
        content = message["content"] if isinstance(message, dict) else message.content
        lines.append(f"{role.upper()}: {content}")
    return "\n\n".join(lines)
