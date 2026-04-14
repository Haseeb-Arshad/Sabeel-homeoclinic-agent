"""
Sabeel Homeo Clinic - AI Voice & Text Chatbot
FastAPI Application Entry Point
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.chat_routes import router as chat_router
from app.api.social_routes import router as social_router
from app.api.twilio_voice_routes import router as twilio_voice_router
from app.api.voice_routes import router as voice_router
from app.api.whatsapp_routes import router as whatsapp_router
from app.api.whatsapp_v2_routes import router as whatsapp_v2_router
from app.core.config import settings

app = FastAPI(
    title="Sabeel Homeo Clinic AI Chatbot",
    description="High-performance AI Voice & Text Chatbot for Sabeel Homeo Clinic",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

cors_origins = settings.cors_origins
allow_all_origins = cors_origins == ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path("static")
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(voice_router)
app.include_router(whatsapp_router)
app.include_router(whatsapp_v2_router)
app.include_router(social_router)
app.include_router(chat_router)
app.include_router(twilio_voice_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint to verify the API is running."""
    return {
        "status": "healthy",
        "service": "Sabeel Homeo Clinic AI Chatbot",
        "version": "1.1.0",
        "channels": {
            "openai": settings.openai_enabled,
            "twilio": settings.twilio_enabled,
            "deepgram": settings.deepgram_enabled,
            "elevenlabs": settings.elevenlabs_enabled,
            "meta": settings.meta_enabled,
            "evolution": settings.evolution_enabled,
        },
    }


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Welcome to Sabeel Homeo Clinic AI Chatbot API",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "voice_websocket": "/ws/media-stream",
            "twilio_voice_webhook": "/twilio/voice/incoming",
            "twilio_whatsapp_webhook": "/webhook/whatsapp",
            "evolution_whatsapp_webhook": "/webhook/evolution",
            "meta_webhook": "/webhook/meta",
            "web_chat": "/api/chat",
            "web_chat_stream": "/api/chat/stream",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
