import base64
import json
from typing import Any

import httpx

from app.core.config import settings


class WhatsAppService:
    """
    WhatsApp Service using Evolution API (Baileys/WAWeb alternative).
    Handles sending text messages, media, and media fetch fallbacks.
    """

    def __init__(self):
        self.base_url = settings.WHATSAPP_API_URL.rstrip("/")
        self.api_key = settings.WHATSAPP_API_KEY
        self.instance = settings.WHATSAPP_INSTANCE_NAME
        self.headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key and self.instance)

    @staticmethod
    def _normalize_number(number: str) -> str:
        if "@" not in number:
            return f"{number}@s.whatsapp.net"
        return number

    @staticmethod
    def _looks_like_base64(value: str) -> bool:
        if not value or not isinstance(value, str):
            return False
        sample = value.split(",", 1)[-1].strip()
        if len(sample) < 32 or len(sample) % 4 != 0:
            return False
        allowed = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=\n\r"
        return all(ch in allowed for ch in sample[:128])

    @classmethod
    def _decode_base64(cls, value: str) -> bytes | None:
        if not value:
            return None
        payload = value.split(",", 1)[-1].strip()
        if not cls._looks_like_base64(payload):
            return None
        try:
            return base64.b64decode(payload)
        except Exception:
            return None

    @classmethod
    def _find_media_base64(cls, payload: Any) -> bytes | None:
        if isinstance(payload, str):
            return cls._decode_base64(payload)
        if isinstance(payload, dict):
            for key in ("base64", "audio", "data", "mediaBase64", "fileBase64"):
                value = payload.get(key)
                decoded = cls._find_media_base64(value)
                if decoded:
                    return decoded
            for value in payload.values():
                decoded = cls._find_media_base64(value)
                if decoded:
                    return decoded
        if isinstance(payload, list):
            for item in payload:
                decoded = cls._find_media_base64(item)
                if decoded:
                    return decoded
        return None

    async def send_text(self, number: str, text: str) -> bool:
        if not self.is_configured:
            print("Evolution API is not configured; cannot send text.")
            return False

        url = f"{self.base_url}/message/sendText/{self.instance}"
        payload = {
            "number": self._normalize_number(number),
            "options": {
                "delay": 1200,
                "presence": "composing",
                "linkPreview": False,
            },
            "textMessage": {
                "text": text,
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=self.headers, timeout=30)
                response.raise_for_status()
                result = response.json()
                return result.get("status") == "SUCCESS"
        except Exception as exc:
            print(f"[ERROR] Evolution API - send_text error: {exc}")
            return False

    async def send_media(self, number: str, media_url: str, caption: str = "", media_type: str = "image") -> bool:
        if not self.is_configured:
            print("Evolution API is not configured; cannot send media.")
            return False

        url = f"{self.base_url}/message/sendMedia/{self.instance}"
        payload = {
            "number": self._normalize_number(number),
            "mediaMessage": {
                "mediatype": media_type,
                "caption": caption,
                "media": media_url,
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=self.headers, timeout=60)
                response.raise_for_status()
                return True
        except Exception as exc:
            print(f"[ERROR] Evolution API - send_media error: {exc}")
            return False

    async def send_audio(self, number: str, audio_url: str) -> bool:
        if not self.is_configured:
            print("Evolution API is not configured; cannot send audio.")
            return False

        url = f"{self.base_url}/message/sendWhatsAppAudio/{self.instance}"
        payload = {
            "number": self._normalize_number(number),
            "audioMessage": {
                "audio": audio_url,
                "ptt": True,
            },
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=self.headers, timeout=60)
                response.raise_for_status()
                return True
        except Exception as exc:
            print(f"[ERROR] Evolution API - send_audio error: {exc}")
            return False

    async def fetch_media_bytes(self, message_payload: dict[str, Any]) -> bytes | None:
        """
        Resolve Evolution webhook media either from inline base64 or by calling the
        official getBase64FromMediaMessage endpoint.
        """
        decoded = self._find_media_base64(message_payload)
        if decoded:
            return decoded

        if not self.is_configured:
            return None

        url = f"{self.base_url}/chat/getBase64FromMediaMessage/{self.instance}"
        payload = {
            "message": message_payload,
            "convertToMp4": False,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=self.headers, timeout=60)
                response.raise_for_status()
        except Exception as exc:
            print(f"[ERROR] Evolution API - fetch_media_bytes error: {exc}")
            return None

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                data = response.json()
            except json.JSONDecodeError:
                data = None
            if data is not None:
                return self._find_media_base64(data)

        body = response.text.strip()
        if body:
            decoded = self._decode_base64(body)
            if decoded:
                return decoded

        if response.content and ("audio/" in content_type or "application/octet-stream" in content_type):
            return response.content
        return None


whatsapp_service = WhatsAppService()
