"""
WhatsApp V2 Routes - Webhook handlers for Evolution API (Baileys/WAWeb)
Handles text messages and voice notes with AI responses.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Request

from app.api.whatsapp_routes import transcribe_audio_async
from app.core.config import settings
from app.services.ai_service import ai_service
from app.services.db_service import db_service
from app.services.elevenlabs_service import elevenlabs_service
from app.services.whatsapp_service import whatsapp_service
from app.utils.audio_utils import cleanup_temp_file, download_audio, save_audio_bytes, save_temp_audio_bytes

router = APIRouter(prefix="/webhook/evolution", tags=["WhatsApp V2"])

STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)


def get_public_audio_url(filename: str, request: Request) -> str:
    if settings.public_base_url:
        return f"{settings.public_base_url}/static/{filename}"
    host = request.headers.get("host", "localhost:8000")
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme or "http")
    return f"{scheme}://{host}/static/{filename}"


def _message_text(message_content: dict) -> str:
    return message_content.get("conversation") or message_content.get("extendedTextMessage", {}).get("text", "")


async def _resolve_evolution_audio_path(msg_data: dict) -> str | None:
    message_content = msg_data.get("message", {})
    audio_msg = message_content.get("audioMessage", {})

    media_url = (
        message_content.get("mediaUrl")
        or audio_msg.get("mediaUrl")
        or audio_msg.get("url")
    )
    if media_url:
        return await download_audio(media_url)

    media_bytes = await whatsapp_service.fetch_media_bytes(msg_data)
    if media_bytes:
        return save_temp_audio_bytes(media_bytes, suffix=".ogg")
    return None


@router.post("")
async def evolution_webhook(request: Request, background_tasks: BackgroundTasks):
    """Main webhook for Evolution API events."""
    data = await request.json()
    event = data.get("event")
    if event != "messages.upsert":
        return {"status": "ignored"}

    msg_data = data.get("data", {})
    key = msg_data.get("key", {})
    if key.get("fromMe", False):
        return {"status": "ignored_self"}

    remote_jid = key.get("remoteJid")
    if not remote_jid:
        return {"status": "ignored"}

    message_content = msg_data.get("message", {})
    text = _message_text(message_content)
    audio_msg = message_content.get("audioMessage")

    if text:
        background_tasks.add_task(handle_text_message, remote_jid, text)
    elif audio_msg:
        background_tasks.add_task(handle_audio_message, remote_jid, msg_data, request)

    return {"status": "received"}


async def handle_text_message(remote_jid: str, text: str):
    """Process text message in the background."""
    try:
        conversation_id = db_service.get_or_create_conversation(
            channel="whatsapp_evolution",
            external_id=remote_jid,
            metadata={"provider": "evolution"},
        )
        messages = db_service.build_conversation_messages(conversation_id, text, limit=20)
        db_service.add_message(conversation_id, "user", text)

        ai_response = await ai_service.generate_response_async(
            messages,
            channel="whatsapp",
            user_contact=remote_jid,
            conversation_id=conversation_id,
        )
        db_service.add_message(conversation_id, "assistant", ai_response)
        await whatsapp_service.send_text(remote_jid, ai_response)
    except Exception as exc:
        print(f"[ERROR] Error handling Evolution text message: {exc}")


async def handle_audio_message(remote_jid: str, msg_data: dict, request: Request):
    """Process audio voice note in the background."""
    loop = asyncio.get_event_loop()
    conversation_id = db_service.get_or_create_conversation(
        channel="whatsapp_evolution",
        external_id=remote_jid,
        metadata={"provider": "evolution"},
    )

    try:
        temp_audio_path = await _resolve_evolution_audio_path(msg_data)
        if not temp_audio_path:
            print("[WARNING] Evolution audio payload did not contain mediaUrl or fetchable media bytes.")
            return

        transcribed_text = await transcribe_audio_async(temp_audio_path)
        await loop.run_in_executor(None, cleanup_temp_file, temp_audio_path)
        if not transcribed_text:
            return

        messages = db_service.build_conversation_messages(conversation_id, transcribed_text, limit=20)
        db_service.add_message(conversation_id, "user", transcribed_text)

        ai_response_text = await ai_service.generate_response_async(
            messages,
            channel="whatsapp",
            user_contact=remote_jid,
            conversation_id=conversation_id,
        )
        db_service.add_message(conversation_id, "assistant", ai_response_text)

        audio_bytes = await elevenlabs_service.text_to_speech_rest_async(ai_response_text)
        if audio_bytes:
            filename = f"whatsapp_reply_{uuid.uuid4().hex}.mp3"
            file_path = STATIC_DIR / filename
            await loop.run_in_executor(None, save_audio_bytes, audio_bytes, str(file_path))

            public_url = get_public_audio_url(filename, request)
            await whatsapp_service.send_audio(remote_jid, public_url)
        else:
            await whatsapp_service.send_text(remote_jid, ai_response_text)
    except Exception as exc:
        print(f"[ERROR] Error handling Evolution audio message: {exc}")
