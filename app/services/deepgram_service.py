"""
Deepgram Service - Live Speech-to-Text Transcription
Handles real-time audio streaming for voice calls.
"""

import logging
from contextlib import AsyncExitStack
from typing import Callable, Optional

from deepgram import DeepgramClient

from app.core.config import settings

logger = logging.getLogger(__name__)


class DeepgramService:
    """
    Deepgram Live Transcription service for real-time STT.
    Designed for Twilio media streams (mulaw 8000hz).
    Uses Deepgram SDK v3+ pattern.
    """

    def __init__(self):
        self.client = DeepgramClient(settings.DEEPGRAM_API_KEY) if settings.deepgram_enabled else None
        self.socket = None
        self.exit_stack = AsyncExitStack()
        self.is_connected = False
        self._on_transcript_callback: Optional[Callable] = None
        self._on_speech_final_callback: Optional[Callable] = None

    async def connect(
        self,
        on_transcript: Optional[Callable] = None,
        on_speech_final: Optional[Callable] = None,
    ):
        """
        Connect to Deepgram Live Transcription API.
        """
        self._on_transcript_callback = on_transcript
        self._on_speech_final_callback = on_speech_final

        if self.client is None:
            logger.warning("Deepgram is not configured; voice transcription is disabled.")
            return False

        try:
            self.socket = await self.exit_stack.enter_async_context(
                self.client.listen.asyncwebsocket.v("1").connect(
                    model="nova-2",
                    language="en-US",
                    encoding="mulaw",
                    sample_rate=8000,
                    channels=1,
                    punctuate=True,
                    interim_results=True,
                    utterance_end_ms=1000,
                    vad_events=True,
                    endpointing=300,
                )
            )

            self.socket.on("open", self._on_open)
            self.socket.on("info", self._on_message)
            self.socket.on("Results", self._on_message)
            self.socket.on("UtteranceEnd", self._on_utterance_end)
            self.socket.on("SpeechStarted", self._on_speech_started)
            self.socket.on("error", self._on_error)
            self.socket.on("close", self._on_close)
            self.socket.on("message", self._on_message)

            self.is_connected = True
            logger.info("Deepgram connected to live transcription")
            return True
        except Exception as exc:
            logger.error("Deepgram connection error: %s", exc)
            return False

    async def send_audio(self, audio_bytes: bytes):
        """Send audio bytes to Deepgram for transcription."""
        if self.socket and self.is_connected:
            try:
                await self.socket.send(audio_bytes)
            except Exception as exc:
                logger.error("Deepgram send error: %s", exc)

    async def close(self):
        """Close the Deepgram connection."""
        if self.exit_stack:
            try:
                await self.exit_stack.aclose()
            except Exception as exc:
                logger.error("Deepgram close error: %s", exc)
            finally:
                self.is_connected = False
                self.socket = None

    def _on_open(self, *args, **kwargs):
        logger.info("Deepgram WebSocket opened")

    async def _on_message(self, result, **kwargs):
        try:
            if hasattr(result, "channel"):
                transcript = result.channel.alternatives[0].transcript
                is_final = result.is_final
                speech_final = result.speech_final

                if transcript and self._on_transcript_callback:
                    await self._on_transcript_callback(transcript, is_final)

                if transcript and speech_final and self._on_speech_final_callback:
                    await self._on_speech_final_callback(transcript)
        except Exception:
            return

    async def _on_utterance_end(self, *args, **kwargs):
        logger.info("Deepgram utterance end detected")

    async def _on_speech_started(self, *args, **kwargs):
        return

    def _on_error(self, *args, **kwargs):
        logger.error("Deepgram error: %s", kwargs.get("error"))

    def _on_close(self, *args, **kwargs):
        self.is_connected = False
        logger.info("Deepgram connection closed")


def create_deepgram_service() -> DeepgramService:
    """Create a new DeepgramService instance."""
    return DeepgramService()
