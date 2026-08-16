from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ConversationMessage(BaseModel):
    # Historical assistant IDs used a UUID plus a role suffix. Keep accepting those
    # persisted clients while new IDs stay within the 36-character primary-key contract.
    id: str = Field(min_length=1, max_length=64)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)


def _empty_history() -> list[ConversationMessage]:
    return []


class CreateRunRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8_000)
    conversation_id: str = Field(min_length=1, max_length=36)
    message_id: str = Field(min_length=1, max_length=36)
    display_name: str | None = Field(default=None, min_length=1, max_length=32)
    history: list[ConversationMessage] = Field(default_factory=_empty_history, max_length=20)
    mode: Literal["quick", "auto", "research"] = "auto"

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not re.fullmatch(r"[\w .'-]{1,32}", normalized, flags=re.UNICODE):
            raise ValueError("Display name contains unsupported characters")
        return normalized


class CreateRunResponse(BaseModel):
    run_id: str
    event_url: str
    cancel_url: str


class RunSnapshot(BaseModel):
    run_id: str
    conversation_id: str
    status: str
    model: str
    answer: str | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class EditMessageRequest(BaseModel):
    replacement: str = Field(min_length=1, max_length=8_000)


class EditMessageResponse(BaseModel):
    conversation_id: str
    removed_message_ids: list[str]


class TurnResult(BaseModel):
    action: Literal["answer", "archive_unavailable", "terminate_conversation", "urgent_safety"]
    answer: str | None = None
    conversation_title: str | None = Field(default=None, min_length=2, max_length=48)

    @field_validator("conversation_title")
    @classmethod
    def normalize_conversation_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        title = " ".join(value.split()).strip(" \"'")
        if "\n" in title or not title:
            raise ValueError("Conversation title must be a single non-empty line")
        return title

    @model_validator(mode="after")
    def validate_answer_shape(self) -> TurnResult:
        if self.action in {"answer", "urgent_safety"} and not self.answer:
            raise ValueError("This action requires answer text")
        if self.action in {"archive_unavailable", "terminate_conversation"} and self.answer:
            raise ValueError("Restricted actions cannot contain generated answer text")
        return self


class EventPayload(BaseModel):
    event_id: int
    run_id: str
    type: str
    created_at: datetime
    payload: dict[str, object]


RunId = Annotated[str, Field(min_length=1, max_length=36)]
