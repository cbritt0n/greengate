from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(..., min_length=1)


class ChatCompletionRequest(BaseModel):
    model: str = Field(..., min_length=1)
    messages: list[ChatMessage] = Field(..., min_length=1)
    temperature: float = Field(1.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, gt=0)
    top_p: float = Field(1.0, ge=0.0, le=1.0)
    stream: bool = False
    user: str | None = None

    @field_validator("messages")
    @classmethod
    def ensure_user_message(cls, messages: list[ChatMessage]) -> list[ChatMessage]:
        if not any(message.role == "user" for message in messages):
            raise ValueError("At least one user message is required")
        return messages
