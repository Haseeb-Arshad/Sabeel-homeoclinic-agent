import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

os.environ["OPENAI_API_KEY"] = "sk-test"
os.environ["TWILIO_ACCOUNT_SID"] = "ACtest"
os.environ["TWILIO_AUTH_TOKEN"] = "authtest"
os.environ["ELEVENLABS_API_KEY"] = "xi-test"
os.environ["DEEPGRAM_API_KEY"] = "dg-test"
os.environ["WHATSAPP_API_URL"] = "http://localhost:8080"
os.environ["WHATSAPP_API_KEY"] = "testkey"

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app


class TestEvolutionAPI(unittest.IsolatedAsyncioTestCase):
    async def test_evolution_webhook_text(self):
        from httpx import ASGITransport, AsyncClient

        payload = {
            "event": "messages.upsert",
            "instance": "sabeel_homeo",
            "data": {
                "key": {
                    "remoteJid": "923001234567@s.whatsapp.net",
                    "fromMe": False,
                    "id": "TEST_ID",
                },
                "message": {
                    "conversation": "Hello Doctor",
                },
                "pushName": "Test User",
            },
        }

        with patch("app.api.whatsapp_v2_routes.ai_service.generate_response_async", new=AsyncMock(return_value="Hello")):
            with patch("app.api.whatsapp_v2_routes.whatsapp_service.send_text", new=AsyncMock(return_value=True)):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                    response = await ac.post("/webhook/evolution", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "received"})

    async def test_evolution_webhook_ignored_event(self):
        from httpx import ASGITransport, AsyncClient

        payload = {
            "event": "connection.update",
            "instance": "sabeel_homeo",
            "data": {"status": "open"},
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/webhook/evolution", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ignored"})

    async def test_evolution_audio_uses_media_url_when_present(self):
        with patch("app.api.whatsapp_v2_routes.download_audio", new=AsyncMock(return_value="temp.ogg")) as download_mock:
            route_module = __import__("app.api.whatsapp_v2_routes", fromlist=["_resolve_evolution_audio_path"])
            path = await route_module._resolve_evolution_audio_path(
                {
                    "message": {
                        "mediaUrl": "https://files.example/audio.ogg",
                        "audioMessage": {},
                    }
                }
            )
        self.assertEqual(path, "temp.ogg")
        download_mock.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
