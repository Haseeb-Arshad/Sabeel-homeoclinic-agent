"""
Social Media Routes (Instagram & Facebook Messenger)
Handles webhook verification and incoming messages from Meta.
"""

import logging

import httpx
from fastapi import APIRouter, BackgroundTasks, Query, Request, Response, status

from app.core.config import settings
from app.services.ai_service import ai_service
from app.services.db_service import db_service

router = APIRouter()
logger = logging.getLogger(__name__)

META_GRAPH_API_URL = "https://graph.facebook.com/v19.0/me/messages"


@router.get("/webhook/meta")
async def verify_webhook(
    mode: str = Query(alias="hub.mode"),
    token: str = Query(alias="hub.verify_token"),
    challenge: str = Query(alias="hub.challenge"),
):
    """Handle Meta's webhook verification challenge."""
    logger.info("Received Meta webhook verification request")

    if mode == "subscribe" and token == settings.META_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")

    return Response(status_code=status.HTTP_403_FORBIDDEN, content="Verification failed")


@router.post("/webhook/meta")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming messages from Instagram and Messenger."""
    try:
        data = await request.json()
        if data.get("object") not in ["page", "instagram"]:
            return Response(status_code=status.HTTP_404_NOT_FOUND)

        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                background_tasks.add_task(start_processing_event, messaging_event)

        return Response(content="EVENT_RECEIVED", status_code=status.HTTP_200_OK)
    except Exception as exc:
        logger.error("Error handling Meta webhook: %s", exc)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def start_processing_event(event: dict):
    """Process a single messaging event."""
    sender_id = event.get("sender", {}).get("id")
    message = event.get("message", {})
    message_text = message.get("text")

    if not sender_id or not message_text:
        logger.debug("Received non-text Meta event or missing sender ID.")
        return

    conversation_id = db_service.get_or_create_conversation(
        channel="meta",
        external_id=sender_id,
        metadata={"provider": "meta"},
    )
    messages = db_service.build_conversation_messages(conversation_id, message_text, limit=20)
    db_service.add_message(conversation_id, "user", message_text)

    ai_response = await ai_service.generate_response_async(
        messages,
        channel="meta",
        user_contact=sender_id,
        conversation_id=conversation_id,
    )
    db_service.add_message(conversation_id, "assistant", ai_response)

    await send_reply(sender_id, ai_response)


async def send_reply(recipient_id: str, text: str):
    """Send a text reply using the Meta Graph API."""
    if not settings.meta_enabled:
        logger.warning("Meta page access token is missing; reply was not sent.")
        return

    params = {"access_token": settings.META_PAGE_ACCESS_TOKEN}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE",
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                META_GRAPH_API_URL,
                params=params,
                json=payload,
                timeout=10,
            )

        if response.status_code != 200:
            logger.error("Failed to send Meta reply: %s - %s", response.status_code, response.text)
    except Exception as exc:
        logger.error("Exception sending Meta reply: %s", exc)
