from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StoredMessage(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20_000)
    state: Literal["complete", "streaming", "failed"] = "complete"
    created_at: datetime


class ConversationWrite(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    title_state: Literal["pending", "generated"]
    pinned: bool = False
    terminated: bool = False
    updated_at: datetime
    messages: list[StoredMessage] = Field(default_factory=list, max_length=100)


class ConversationRead(ConversationWrite):
    id: str
    revision: int
