"""
Twilio request validation helpers.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request
from twilio.request_validator import RequestValidator

from app.core.config import settings


def _request_url_for_validation(request: Request) -> str:
    """Build URL Twilio used to sign the request."""
    if settings.PUBLIC_BASE_URL:
        query = str(request.query_params)
        if query:
            return f"{settings.PUBLIC_BASE_URL.rstrip('/')}{request.url.path}?{query}"
        return f"{settings.PUBLIC_BASE_URL.rstrip('/')}{request.url.path}"

    return str(request.url)


def validate_twilio_request(request: Request, params: dict[str, str]) -> bool:
    """Validate incoming Twilio webhook signature.

    If signature validation is disabled via config, this always returns True.
    """
    if not settings.TWILIO_VERIFY_SIGNATURE:
        return True

    signature = request.headers.get("X-Twilio-Signature", "")
    if not signature:
        return False

    validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
    url = _request_url_for_validation(request)
    return validator.validate(url, params, signature)
