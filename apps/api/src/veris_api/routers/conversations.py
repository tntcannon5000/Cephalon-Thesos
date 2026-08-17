from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from veris_api.auth import require_csrf, require_identity
from veris_api.conversation_schemas import ConversationRead, ConversationWrite
from veris_api.db.conversations import (
    ConversationOwnershipError,
    delete_conversation,
    list_conversations,
    upsert_conversation,
)

router = APIRouter(prefix="/api/v1/conversations")


@router.get("", response_model=list[ConversationRead])
async def get_conversations(request: Request) -> list[ConversationRead]:
    identity = await require_identity(request)
    return await list_conversations(identity.user_id)


@router.put("/{conversation_id}", response_model=ConversationRead)
async def put_conversation(
    conversation_id: str,
    body: ConversationWrite,
    request: Request,
) -> ConversationRead:
    identity = await require_identity(request)
    require_csrf(request, identity)
    try:
        return await upsert_conversation(conversation_id, identity.user_id, body)
    except ConversationOwnershipError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_conversation(conversation_id: str, request: Request) -> Response:
    identity = await require_identity(request)
    require_csrf(request, identity)
    if not await delete_conversation(conversation_id, identity.user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
