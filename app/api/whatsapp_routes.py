"""
WhatsApp Routes - Webhook handlers for Twilio WhatsApp
Handles text messages and voice notes with AI responses.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Form, Request
from fastapi.responses import PlainTextResponse
from openai import OpenAI
from twilio.rest import Client as TwilioClient
from twilio.twiml.messaging_response import MessagingResponse

from app.core.config import settings
from app.services.ai_service import ai_service
from app.services.db_service import db_service
from app.services.elevenlabs_service import elevenlabs_service
from app.services.twilio_security_service import validate_twilio_request
from app.utils.audio_utils import cleanup_temp_file, download_audio, save_audio_bytes

router = APIRouter(prefix="/webhook", tags=["WhatsApp"])

STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)

def _openai_client() -> OpenAI | None:
    if not settings.openai_enabled:
        return None

    kwargs = {}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    if settings.openai_default_headers:
        kwargs["default_headers"] = settings.openai_default_headers
    return OpenAI(api_key=settings.OPENAI_API_KEY, **kwargs)


openai_client = _openai_client()


def _twilio_client() -> TwilioClient | None:
    if not settings.twilio_enabled:
        return None
    return TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


async def transcribe_audio_async(audio_path: str) -> Optional[str]:
    """Transcribe audio file using OpenAI Whisper API."""
    if openai_client is None:
        return None

    loop = asyncio.get_event_loop()

    def _transcribe():
        try:
            with open(audio_path, "rb") as audio_file:
                transcript = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ur",
                )
            return transcript.text
        except Exception as exc:
            print(f"[ERROR] Whisper transcription error: {exc}")
            return None

    return await loop.run_in_executor(None, _transcribe)


def get_public_audio_url(filename: str, request: Request) -> str:
    """Generate public URL for an audio file."""
    if settings.public_base_url:
        return f"{settings.public_base_url}/static/{filename}"
    host = request.headers.get("host", "localhost:8000")
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme or "http")
    return f"{scheme}://{host}/static/{filename}"


def _twilio_media_auth(url: str) -> tuple[str, str] | None:
    hostname = (urlparse(url).hostname or "").lower()
    if "twilio.com" not in hostname or not settings.twilio_enabled:
        return None
    return settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN


def _twiml_response(response_text: str, audio_url: str | None = None) -> PlainTextResponse:
    twiml = MessagingResponse()
    message = twiml.message(response_text)
    if audio_url:
        message.media(audio_url)
    return PlainTextResponse(content=str(twiml), media_type="application/xml")


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(default=""),
    NumMedia: str = Form(default="0"),
    MediaUrl0: Optional[str] = Form(default=None),
    MediaContentType0: Optional[str] = Form(default=None),
):
    """Twilio WhatsApp webhook endpoint."""
    incoming_form = await request.form()
    params_for_validation = {k: str(v) for k, v in incoming_form.items()}
    if not validate_twilio_request(request, params_for_validation):
        return PlainTextResponse(content="Invalid signature", status_code=403)

    response_text = ""
    audio_url = None
    loop = asyncio.get_event_loop()
    conversation_id = db_service.get_or_create_conversation(
        channel="whatsapp",
        external_id=From,
        metadata={"provider": "twilio_whatsapp"},
    )

    try:
        if int(NumMedia) > 0 and MediaUrl0:
            temp_audio_path = await download_audio(MediaUrl0, auth=_twilio_media_auth(MediaUrl0))

            if temp_audio_path:
                transcribed_text = await transcribe_audio_async(temp_audio_path)
                await loop.run_in_executor(None, cleanup_temp_file, temp_audio_path)

                if transcribed_text:
                    messages = db_service.build_conversation_messages(conversation_id, transcribed_text, limit=20)
                    db_service.add_message(conversation_id, "user", transcribed_text)
                    response_text = await ai_service.generate_response_async(
                        messages,
                        channel="whatsapp",
                        user_contact=From,
                        conversation_id=conversation_id,
                    )

                    audio_bytes = await elevenlabs_service.text_to_speech_rest_async(
                        response_text,
                        output_format="mp3_44100_128",
                    )

                    if audio_bytes:
                        filename = f"response_{uuid.uuid4().hex[:8]}.mp3"
                        audio_path = STATIC_DIR / filename
                        saved = await loop.run_in_executor(None, save_audio_bytes, audio_bytes, str(audio_path))
                        if saved:
                            audio_url = get_public_audio_url(filename, request)
                else:
                    response_text = "Maaf kijiye, aapki voice note samajh nahi aayi. Kya aap dobara bol sakte hain?"
            else:
                response_text = "Voice note download nahi ho saki. Please dobara try karein."
        else:
            if Body.strip():
                messages = db_service.build_conversation_messages(conversation_id, Body, limit=20)
                db_service.add_message(conversation_id, "user", Body)
                response_text = await ai_service.generate_response_async(
                    messages,
                    channel="whatsapp",
                    user_contact=From,
                    conversation_id=conversation_id,
                )
            else:
                response_text = "Assalam o Alaikum! Sabeel Homeo Clinic mein aapka swagat hai. Main aapki kaise madad kar sakti hoon?"

        db_service.add_message(conversation_id, "assistant", response_text)

        sender = settings.TWILIO_WHATSAPP_NUMBER or settings.TWILIO_PHONE_NUMBER
        twilio_client = _twilio_client()
        if not sender or twilio_client is None:
            return _twiml_response(response_text, audio_url)

        formatted_sender = sender if sender.startswith("whatsapp:") else f"whatsapp:{sender}"

        def send_twilio_message():
            if audio_url:
                twilio_client.messages.create(
                    from_=formatted_sender,
                    to=From,
                    media_url=[audio_url],
                    body=response_text,
                )
            else:
                twilio_client.messages.create(
                    from_=formatted_sender,
                    to=From,
                    body=response_text,
                )

        await loop.run_in_executor(None, send_twilio_message)
        return PlainTextResponse(
            content="<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response></Response>",
            media_type="application/xml",
        )
    except Exception as exc:
        print(f"[ERROR] WhatsApp webhook error: {exc}")
        return _twiml_response("Sorry, there was an error processing your message. Please try again.")


@router.get("/whatsapp")
async def whatsapp_webhook_verify(request: Request):
    """Simple liveness endpoint for initial webhook setup checks."""
    return PlainTextResponse(content="Webhook is active", status_code=200)
