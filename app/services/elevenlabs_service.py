"""
ElevenLabs Service - Text-to-Speech
Provides both WebSocket streaming (for voice calls) and REST API (for WhatsApp).
"""

import base64
import json
from typing import AsyncGenerator, Optional

import aiohttp
import requests

from app.core.config import settings


class ElevenLabsService:
    """
    ElevenLabs TTS service with WebSocket streaming and REST API support.
    Optimized for real-time voice applications.
    """

    DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
    DEFAULT_MODEL_ID = "eleven_multilingual_v2"
    WS_URL = "wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"
    REST_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    def __init__(self, voice_id: Optional[str] = None):
        self.api_key = settings.ELEVENLABS_API_KEY
        self.voice_id = voice_id or settings.ELEVENLABS_VOICE_ID or self.DEFAULT_VOICE_ID
        self.model_id = settings.ELEVENLABS_MODEL_ID or self.DEFAULT_MODEL_ID
        self.ws_connection = None
        self.is_streaming = False
        self._should_stop = False

    async def stream_text_to_speech(
        self,
        text: str,
        output_format: str = "ulaw_8000",
    ) -> AsyncGenerator[bytes, None]:
        """Stream text to speech via WebSocket."""
        if not self.api_key:
            return

        url = self.WS_URL.format(voice_id=self.voice_id)
        url += f"?model_id={self.model_id}&output_format={output_format}"
        self._should_stop = False

        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url, headers={"xi-api-key": self.api_key}) as ws:
                    self.ws_connection = ws
                    self.is_streaming = True

                    await ws.send_json(
                        {
                            "text": " ",
                            "voice_settings": {
                                "stability": 0.5,
                                "similarity_boost": 0.75,
                                "style": 0.0,
                                "use_speaker_boost": True,
                            },
                            "xi_api_key": self.api_key,
                        }
                    )
                    await ws.send_json({"text": text, "try_trigger_generation": True})
                    await ws.send_json({"text": ""})

                    async for msg in ws:
                        if self._should_stop:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if "audio" in data and data["audio"]:
                                yield base64.b64decode(data["audio"])
                            if data.get("isFinal"):
                                break
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            break
        except Exception as exc:
            print(f"ElevenLabs streaming error: {exc}")
        finally:
            self.is_streaming = False
            self.ws_connection = None

    def stop_streaming(self):
        """Stop the current streaming session (for barge-in)."""
        self._should_stop = True

    def text_to_speech_rest(
        self,
        text: str,
        output_format: str = "mp3_44100_128",
    ) -> Optional[bytes]:
        """Generate speech using REST API."""
        if not self.api_key:
            return None

        url = self.REST_URL.format(voice_id=self.voice_id)
        url += f"?output_format={output_format}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        }

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                return response.content
            print(f"ElevenLabs REST error: {response.status_code} - {response.text}")
        except Exception as exc:
            print(f"ElevenLabs REST error: {exc}")
        return None

    async def text_to_speech_rest_async(
        self,
        text: str,
        output_format: str = "mp3_44100_128",
    ) -> Optional[bytes]:
        """Async version of REST API TTS."""
        if not self.api_key:
            return None

        url = self.REST_URL.format(voice_id=self.voice_id)
        url += f"?output_format={output_format}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:
                    if response.status == 200:
                        return await response.read()
                    error = await response.text()
                    print(f"ElevenLabs REST error: {response.status} - {error}")
        except Exception as exc:
            print(f"ElevenLabs REST async error: {exc}")
        return None


def create_elevenlabs_service(voice_id: Optional[str] = None) -> ElevenLabsService:
    """Create a new ElevenLabsService instance."""
    return ElevenLabsService(voice_id)


elevenlabs_service = ElevenLabsService()
