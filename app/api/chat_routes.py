"""
Website chatbot routes.
Provides standard JSON and SSE streaming responses.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.ai_service import ai_service
from app.services.db_service import db_service

router = APIRouter(prefix="/api/chat", tags=["Website Chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    conversation_id: str = ""
    user_name: str = ""
    user_phone: str = ""


class ChatResponse(BaseModel):
    conversation_id: str
    response: str


def _ensure_conversation(conversation_id: str) -> str:
    if conversation_id:
        return conversation_id
    return db_service.create_conversation(channel="webchat", metadata={"source": "website"})


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    conversation_id = _ensure_conversation(request.conversation_id)
    messages = db_service.build_conversation_messages(conversation_id, request.message, limit=20)
    db_service.add_message(conversation_id, "user", request.message)

    response_text = await ai_service.generate_response_async(
        messages,
        is_voice=False,
        channel="webchat",
        user_contact=request.user_phone,
        user_name=request.user_name,
        conversation_id=conversation_id,
    )

    db_service.add_message(conversation_id, "assistant", response_text)
    return ChatResponse(conversation_id=conversation_id, response=response_text)


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    conversation_id = _ensure_conversation(request.conversation_id)
    messages = db_service.build_conversation_messages(conversation_id, request.message, limit=20)
    db_service.add_message(conversation_id, "user", request.message)

    async def event_stream() -> AsyncGenerator[str, None]:
        meta = {"conversation_id": conversation_id, "event": "meta"}
        yield f"data: {json.dumps(meta)}\n\n"

        assistant_chunks: list[str] = []
        async for chunk in ai_service.generate_response_stream_async(
            messages,
            is_voice=False,
            channel="webchat",
            user_contact=request.user_phone,
            user_name=request.user_name,
            conversation_id=conversation_id,
        ):
            assistant_chunks.append(chunk)
            yield f"data: {json.dumps({'event': 'delta', 'text': chunk})}\n\n"

        final_text = "".join(assistant_chunks).strip()
        if final_text:
            db_service.add_message(conversation_id, "assistant", final_text)

        yield f"data: {json.dumps({'event': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
