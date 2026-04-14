import json
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch

os.environ["OPENAI_API_KEY"] = "sk-test"
os.environ["TWILIO_ACCOUNT_SID"] = "ACtest"
os.environ["TWILIO_AUTH_TOKEN"] = "authtest"
os.environ["ELEVENLABS_API_KEY"] = "xi-test"
os.environ["DEEPGRAM_API_KEY"] = "dg-test"

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from app.services.ai_service import AIService


class TestChatbot(unittest.IsolatedAsyncioTestCase):
    async def test_health_check(self):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "healthy")
        self.assertIn("channels", response.json())

    async def test_whatsapp_webhook_missing_signature(self):
        from httpx import ASGITransport, AsyncClient

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post("/webhook/whatsapp", data={})
        self.assertEqual(response.status_code, 422)

    async def test_chat_history_is_reused_for_follow_up(self):
        from httpx import ASGITransport, AsyncClient

        captured_messages = []

        async def fake_generate(messages, **kwargs):
            captured_messages.append(messages)
            return f"reply-{len(captured_messages)}"

        with patch("app.api.chat_routes.ai_service.generate_response_async", side_effect=fake_generate):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                first = await ac.post("/api/chat", json={"message": "What are your timings?"})
                conversation_id = first.json()["conversation_id"]
                second = await ac.post(
                    "/api/chat",
                    json={"message": "And your address?", "conversation_id": conversation_id},
                )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(captured_messages), 2)
        second_call_messages = captured_messages[1]
        self.assertTrue(any(message["content"] == "What are your timings?" for message in second_call_messages))
        self.assertTrue(any(message["content"] == "reply-1" for message in second_call_messages))
        self.assertEqual(second_call_messages[-1]["content"], "And your address?")

    async def test_streaming_endpoint_emits_meta_and_done(self):
        from httpx import ASGITransport, AsyncClient

        async def fake_stream(messages, **kwargs):
            for chunk in ["Hello ", "world"]:
                yield chunk

        with patch("app.api.chat_routes.ai_service.generate_response_stream_async", side_effect=fake_stream):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post("/api/chat/stream", json={"message": "Hello"})

        self.assertEqual(response.status_code, 200)
        body = response.text
        self.assertIn('"event": "meta"', body)
        self.assertIn('"event": "done"', body)
        self.assertIn("Hello ", body)

    async def test_appointment_booking_mock(self):
        service = AIService()
        mock_create = AsyncMock()
        service._async_client = AsyncMock()
        service._async_client.chat.completions.create = mock_create

        from openai.types.chat import ChatCompletion, ChatCompletionMessage, ChatCompletionMessageToolCall
        from openai.types.chat.chat_completion import Choice
        from openai.types.chat.chat_completion_message_tool_call import Function

        tool_call = ChatCompletionMessageToolCall(
            id="call_123",
            function=Function(
                name="book_appointment",
                arguments=json.dumps({"name": "Ali", "time": "5pm", "reason": "Fever"}),
            ),
            type="function",
        )

        message_with_tool = ChatCompletionMessage(role="assistant", content=None, tool_calls=[tool_call])
        final_message = ChatCompletionMessage(role="assistant", content="Appointment booked for Ali at 5pm.")

        choice1 = Choice(finish_reason="tool_calls", index=0, message=message_with_tool)
        choice2 = Choice(finish_reason="stop", index=0, message=final_message)

        response1 = ChatCompletion(id="resp_1", choices=[choice1], created=123, model="gpt-4o-mini", object="chat.completion")
        response2 = ChatCompletion(id="resp_2", choices=[choice2], created=124, model="gpt-4o-mini", object="chat.completion")

        mock_create.side_effect = [response1, response2]

        conversation = [{"role": "user", "content": "Book appointment for Ali at 5pm for fever"}]
        result = await service.generate_response_async(conversation)

        self.assertIn("Appointment booked for Ali at 5pm", result)
        self.assertEqual(mock_create.call_count, 2)


if __name__ == "__main__":
    unittest.main()
