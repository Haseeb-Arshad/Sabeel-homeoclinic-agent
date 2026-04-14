"""
Twilio Voice HTTP routes.
Provides TwiML entrypoint that connects calls to the media WebSocket stream.
"""

from __future__ import annotations

from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.core.config import settings
from app.services.twilio_security_service import validate_twilio_request

router = APIRouter(prefix="/twilio/voice", tags=["Twilio Voice"])


def _build_stream_url(request: Request) -> str:
    if settings.PUBLIC_BASE_URL:
        base = settings.PUBLIC_BASE_URL.rstrip("/")
        parsed = urlparse(base)
        scheme = "wss" if parsed.scheme == "https" else "ws"
        host = parsed.netloc
    else:
        forwarded_proto = request.headers.get("x-forwarded-proto")
        scheme = "wss" if (forwarded_proto == "https" or request.url.scheme == "https") else "ws"
        host = request.headers.get("host", "localhost:8000")

    return f"{scheme}://{host}/ws/media-stream"


@router.post("/incoming")
async def incoming_voice_call(request: Request):
    """Twilio webhook for incoming calls. Returns TwiML with <Connect><Stream/>."""
    form_data = await request.form()
    params = {k: str(v) for k, v in form_data.items()}

    if not validate_twilio_request(request, params):
        return PlainTextResponse("Invalid signature", status_code=403)

    response = VoiceResponse()
    response.say(
        "Assalam o Alaikum. Welcome to Sabeel Homeo Clinic. Please speak after the beep.",
        voice="alice",
        language="en-US",
    )

    connect = Connect()
    connect.stream(url=_build_stream_url(request))
    response.append(connect)

    return PlainTextResponse(str(response), media_type="application/xml")


@router.post("/status")
async def call_status_callback(request: Request):
    """Capture Twilio call status callbacks."""
    form_data = await request.form()
    params = {k: str(v) for k, v in form_data.items()}

    if not validate_twilio_request(request, params):
        return PlainTextResponse("Invalid signature", status_code=403)

    return {"status": "received"}
