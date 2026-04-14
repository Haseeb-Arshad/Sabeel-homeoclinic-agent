"""
API module - Routes for webhooks
"""

from .voice_routes import router as voice_router
from .whatsapp_routes import router as whatsapp_router

__all__ = ["voice_router", "whatsapp_router"]

