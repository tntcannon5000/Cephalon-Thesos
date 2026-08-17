from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import delete, select

from veris_api.conversation_schemas import ConversationRead, ConversationWrite, StoredMessage
from veris_api.db.models import (
    ConversationMessageRecord,
    ConversationRecord,
    MessageControl,
)
from veris_api.db.session import get_session_factory


class ConversationOwnershipError(Exception):
    pass


async def list_conversations(user_id: str) -> list[ConversationRead]:
    async with get_session_factory()() as session:
        conversations = list(
            await session.scalars(
                select(ConversationRecord)
                .where(ConversationRecord.user_id == user_id)
                .order_by(ConversationRecord.updated_at.desc())
                .limit(100)
            )
        )
        if not conversations:
            return []
        conversation_ids = [item.id for item in conversations]
        messages = list(
            await session.scalars(
                select(ConversationMessageRecord)
                .where(ConversationMessageRecord.conversation_id.in_(conversation_ids))
                .order_by(
                    ConversationMessageRecord.conversation_id,
                    ConversationMessageRecord.ordinal,
                )
            )
        )
        by_conversation: dict[str, list[StoredMessage]] = {
            conversation_id: [] for conversation_id in conversation_ids
        }
        for message in messages:
            by_conversation[message.conversation_id].append(
                StoredMessage(
                    id=message.id,
                    role=cast(Literal["user", "assistant"], message.role),
                    content=message.content,
                    state=cast(Literal["complete", "streaming", "failed"], message.state),
                    created_at=message.created_at,
                )
            )
        return [
            ConversationRead(
                id=conversation.id,
                title=conversation.title,
                title_state=cast(Literal["pending", "generated"], conversation.title_state),
                pinned=conversation.pinned,
                terminated=conversation.terminated,
                revision=conversation.revision,
                updated_at=conversation.updated_at,
                messages=by_conversation[conversation.id],
            )
            for conversation in conversations
        ]


async def upsert_conversation(
    conversation_id: str,
    user_id: str,
    body: ConversationWrite,
) -> ConversationRead:
    now = datetime.now(UTC)
    async with get_session_factory()() as session, session.begin():
        conversation = await session.get(
            ConversationRecord,
            conversation_id,
            with_for_update=True,
        )
        if conversation is not None and conversation.user_id != user_id:
            raise ConversationOwnershipError
        if conversation is None:
            conversation = ConversationRecord(
                id=conversation_id,
                user_id=user_id,
                title=body.title,
                title_state=body.title_state,
                pinned=body.pinned,
                terminated=body.terminated,
                revision=1,
                created_at=now,
                updated_at=body.updated_at,
            )
            session.add(conversation)
            await session.flush()
        else:
            active_termination = await session.scalar(
                select(MessageControl.id).where(
                    MessageControl.user_id == user_id,
                    MessageControl.conversation_id == conversation_id,
                    MessageControl.active.is_(True),
                    MessageControl.safety_action == "terminate_conversation",
                )
            )
            conversation.title = body.title
            conversation.title_state = body.title_state
            conversation.pinned = body.pinned
            conversation.terminated = body.terminated or active_termination is not None
            conversation.updated_at = max(body.updated_at, now)
            conversation.revision += 1
            await session.execute(
                delete(ConversationMessageRecord).where(
                    ConversationMessageRecord.conversation_id == conversation_id
                )
            )
        for ordinal, message in enumerate(body.messages, start=1):
            if message.state == "streaming" or not message.content.strip():
                continue
            session.add(
                ConversationMessageRecord(
                    id=message.id,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    ordinal=ordinal,
                    role=message.role,
                    content=message.content,
                    state=message.state,
                    created_at=message.created_at,
                )
            )
        await session.flush()
        return ConversationRead(
            id=conversation.id,
            title=conversation.title,
            title_state=cast(Literal["pending", "generated"], conversation.title_state),
            pinned=conversation.pinned,
            terminated=conversation.terminated,
            revision=conversation.revision,
            updated_at=conversation.updated_at,
            messages=[message for message in body.messages if message.state != "streaming"],
        )


async def delete_conversation(conversation_id: str, user_id: str) -> bool:
    async with get_session_factory()() as session, session.begin():
        conversation = await session.get(
            ConversationRecord,
            conversation_id,
            with_for_update=True,
        )
        if conversation is None or conversation.user_id != user_id:
            return False
        await session.execute(
            delete(MessageControl).where(
                MessageControl.user_id == user_id,
                MessageControl.conversation_id == conversation_id,
            )
        )
        await session.delete(conversation)
        return True
