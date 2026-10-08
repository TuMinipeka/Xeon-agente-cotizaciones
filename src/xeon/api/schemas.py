from __future__ import annotations

from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8_000)
    conversation_id: UUID = Field(default_factory=uuid4)


class ChatResponse(BaseModel):
    conversation_id: UUID
    reply: str
    provider: str
    model: str


class HealthResponse(BaseModel):
    status: str
    environment: str
    provider: str
    model: str
