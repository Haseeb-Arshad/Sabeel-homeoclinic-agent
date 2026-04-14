"""
AI service for Sabeel Homeo Clinic assistant.
Provides clinic-focused responses with tool calling and website-grounded context.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.appointment_service import appointment_service
from app.services.knowledge_service import knowledge_service


CLINIC_FACTS = """
Clinic name: Sabeel Homeo Clinic
Primary phone/WhatsApp: 0300-5125394
Alternate phone: 051-4940734
Address: B-880, Satellite Town Near National Market, Rawalpindi, Pakistan.
Opening hours: Monday-Thursday and Saturday-Sunday, 11:00 AM-1:30 PM and 5:00 PM-9:00 PM.
Friday: Closed.
Lahore visit note: second week of every month, around 11:00 AM-4:00 PM.
Overseas consults: online consultation available; shipping medicines may be restricted.
Legal policy: No guaranteed cure claims; information is not a replacement for medical diagnosis.
""".strip()


SYSTEM_PROMPT = """
You are the official AI assistant for Sabeel Homeo Clinic.

Rules:
1) Only answer questions related to Sabeel Homeo Clinic, its treatments, appointments, timings, contact details, website content, and patient guidance.
2) If asked off-topic (coding, finance, politics, etc.), politely refuse and redirect to clinic support.
3) Do NOT promise a guaranteed cure. Follow the legal disclaimer language.
4) Never prescribe medicines or dosage as a replacement for clinical consultation.
5) For emergency symptoms (severe chest pain, breathing distress, stroke signs, heavy bleeding, unconsciousness), instruct immediate emergency care first.
6) For appointments, collect missing details and then call create_appointment_request.
7) Appointment status is pending until clinic staff confirms.
8) Respond in English or Roman Urdu matching user language.
9) Keep responses concise, empathetic, and practical.
10) Use only the provided clinic facts and context snippets when stating factual details.
""".strip()


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_appointment_request",
            "description": "Create a pending appointment request for clinic staff confirmation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Patient full name."},
                    "phone": {"type": "string", "description": "Phone number with country code if possible."},
                    "preferred_date": {"type": "string", "description": "Preferred appointment date."},
                    "preferred_time": {"type": "string", "description": "Preferred appointment time window."},
                    "reason": {"type": "string", "description": "Condition or concern for consultation."},
                },
                "required": ["name", "phone", "preferred_date", "preferred_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Backward-compatible alias for appointment creation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "time": {"type": "string"},
                    "reason": {"type": "string"},
                    "phone": {"type": "string"},
                },
                "required": ["name", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_clinic_information",
            "description": "Return canonical clinic details for facts and contact questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": ["timings", "contact", "address", "lahore_visit", "disclaimer", "overseas"],
                    }
                },
                "required": ["topic"],
            },
        },
    },
]

EMERGENCY_KEYWORDS = (
    "chest pain",
    "breathing distress",
    "stroke",
    "heavy bleeding",
    "unconscious",
    "not breathing",
    "severe bleeding",
)

APPOINTMENT_KEYWORDS = (
    "appointment",
    "book",
    "booking",
    "slot",
    "consultation",
    "visit",
)


def _clinic_information(topic: str) -> str:
    data = {
        "timings": "Clinic hours: Monday-Thursday and Saturday-Sunday 11:00 AM-1:30 PM and 5:00 PM-9:00 PM. Friday closed.",
        "contact": "Call or WhatsApp: 0300-5125394, phone: 051-4940734.",
        "address": "B-880, Satellite Town Near National Market, Rawalpindi, Pakistan.",
        "lahore_visit": "Lahore visit is generally in the second week of each month around 11:00 AM-4:00 PM. Confirm via phone before visiting.",
        "disclaimer": "Clinic does not guarantee cure outcomes. Website content is informational and does not replace professional diagnosis.",
        "overseas": "Overseas online consultation is available. Shipping medicines may be restricted; clinic provides consultation guidance.",
    }
    return data.get(topic, "Please contact clinic support at 0300-5125394 for the latest details.")


class AIService:
    """Core LLM orchestration with tool handling and context retrieval."""

    def __init__(self):
        self._async_client: AsyncOpenAI | None = None
        self.model = settings.OPENAI_MODEL

    @staticmethod
    def _client_kwargs() -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        if settings.openai_default_headers:
            kwargs["default_headers"] = settings.openai_default_headers
        return kwargs

    def _client(self) -> AsyncOpenAI | None:
        if not settings.openai_enabled:
            return None
        if not self._async_client:
            self._async_client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                **self._client_kwargs(),
            )
        return self._async_client

    @staticmethod
    def _latest_user_query(messages: list[dict[str, str]]) -> str:
        for message in reversed(messages):
            if message.get("role") == "user":
                return message.get("content", "")
        return ""

    @staticmethod
    def _needs_tooling(user_query: str) -> bool:
        lowered = user_query.lower()
        return any(keyword in lowered for keyword in APPOINTMENT_KEYWORDS)

    @staticmethod
    def _fallback_response(user_query: str) -> str:
        lowered = user_query.lower()

        if any(keyword in lowered for keyword in EMERGENCY_KEYWORDS):
            return (
                "This may be an emergency. Please seek immediate emergency medical care or call local emergency "
                "services right now. After stabilization, we can help with clinic follow-up."
            )
        if "time" in lowered or "timing" in lowered or "hours" in lowered or "open" in lowered:
            return _clinic_information("timings")
        if "contact" in lowered or "phone" in lowered or "call" in lowered or "whatsapp" in lowered:
            return _clinic_information("contact")
        if "address" in lowered or "location" in lowered or "where" in lowered:
            return _clinic_information("address")
        if "lahore" in lowered:
            return _clinic_information("lahore_visit")
        if "overseas" in lowered or "online" in lowered:
            return _clinic_information("overseas")
        if "appointment" in lowered or "book" in lowered:
            return (
                "Please share your full name, phone number, preferred date, preferred time, and reason for visit. "
                "Clinic staff will confirm the slot on call or WhatsApp."
            )
        return (
            "Assalam o Alaikum. I can help with Sabeel Homeo Clinic timings, contact details, appointments, "
            "and general patient guidance. You can also call or WhatsApp 0300-5125394."
        )

    async def _build_system_prompt(self, user_query: str, is_voice: bool = False) -> str:
        snippets = await knowledge_service.retrieve_relevant_content(user_query, top_k=5)
        context_block = knowledge_service.format_context(snippets)

        prompt_parts = [SYSTEM_PROMPT, "", "Clinic Facts:", CLINIC_FACTS]
        if context_block:
            prompt_parts.extend(["", "Website Context Snippets:", context_block])
        if is_voice:
            prompt_parts.append("\nVoice mode: keep each reply under 2 short sentences.")

        return "\n".join(prompt_parts)

    async def _execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
        *,
        channel: str,
        conversation_id: str,
        user_contact: str,
    ) -> str:
        if tool_name == "create_appointment_request":
            result = appointment_service.create_pending_request(
                name=args.get("name", "Patient"),
                phone=args.get("phone", user_contact or ""),
                preferred_date=args.get("preferred_date", "next available"),
                preferred_time=args.get("preferred_time", "next available"),
                reason=args.get("reason", "Consultation"),
                channel=channel,
                conversation_id=conversation_id,
            )
            return json.dumps(result)

        if tool_name == "book_appointment":
            time_text = args.get("time", "next available")
            result = appointment_service.create_pending_request(
                name=args.get("name", "Patient"),
                phone=args.get("phone", user_contact or ""),
                preferred_date=time_text,
                preferred_time=time_text,
                reason=args.get("reason", "Consultation"),
                channel=channel,
                conversation_id=conversation_id,
            )
            return json.dumps(result)

        if tool_name == "get_clinic_information":
            topic = str(args.get("topic", "contact"))
            return _clinic_information(topic)

        return "Tool not implemented."

    async def _generate_async_internal(
        self,
        messages: list[dict[str, str]],
        *,
        is_voice: bool,
        channel: str,
        user_contact: str,
        user_name: str,
        conversation_id: str,
    ) -> str:
        client = self._client()
        user_query = self._latest_user_query(messages)
        if client is None:
            return self._fallback_response(user_query)

        system_prompt = await self._build_system_prompt(user_query, is_voice=is_voice)

        conversation: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        conversation.extend(messages)

        response = await client.chat.completions.create(
            model=self.model,
            messages=conversation,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=140 if is_voice else 380,
            temperature=0.3,
        )

        assistant_message = response.choices[0].message

        if assistant_message.tool_calls:
            tool_results = []
            for tool_call in assistant_message.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                tool_output = await self._execute_tool(
                    tool_call.function.name,
                    args,
                    channel=channel,
                    conversation_id=conversation_id,
                    user_contact=user_contact,
                )

                tool_results.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": tool_output,
                    }
                )

            conversation.append(assistant_message.model_dump())
            conversation.extend(tool_results)

            final_response = await client.chat.completions.create(
                model=self.model,
                messages=conversation,
                max_tokens=140 if is_voice else 380,
                temperature=0.3,
            )
            return final_response.choices[0].message.content or ""

        return assistant_message.content or ""

    async def generate_response_stream_async(
        self,
        messages: list[dict[str, str]],
        *,
        is_voice: bool = False,
        channel: str = "unknown",
        user_contact: str = "",
        user_name: str = "",
        conversation_id: str = "",
    ) -> AsyncGenerator[str, None]:
        user_query = self._latest_user_query(messages)

        if self._needs_tooling(user_query):
            text = await self.generate_response_async(
                messages,
                is_voice=is_voice,
                channel=channel,
                user_contact=user_contact,
                user_name=user_name,
                conversation_id=conversation_id,
            )
            for chunk in self._chunk_text(text):
                yield chunk
            return

        client = self._client()
        if client is None:
            for chunk in self._chunk_text(self._fallback_response(user_query)):
                yield chunk
            return

        try:
            system_prompt = await self._build_system_prompt(user_query, is_voice=is_voice)
            conversation: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
            conversation.extend(messages)

            stream = await client.chat.completions.create(
                model=self.model,
                messages=conversation,
                max_tokens=140 if is_voice else 380,
                temperature=0.3,
                stream=True,
            )

            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                text = delta.content or ""
                if text:
                    yield text
        except Exception as exc:
            print(f"[ERROR] AIService Streaming Error: {exc}")
            for chunk in self._chunk_text(
                "Maaf kijiye, abhi technical issue hai. Please thori der baad dobara try karein."
            ):
                yield chunk

    @staticmethod
    def _chunk_text(text: str, chunk_size: int = 18) -> list[str]:
        if not text:
            return []
        words = text.split()
        chunks: list[str] = []
        bucket: list[str] = []
        for word in words:
            bucket.append(word)
            if len(bucket) >= chunk_size:
                chunks.append(" ".join(bucket) + " ")
                bucket = []
        if bucket:
            chunks.append(" ".join(bucket))
        return chunks

    async def generate_response_async(
        self,
        messages: list[dict[str, str]],
        is_voice: bool = False,
        channel: str = "unknown",
        user_contact: str = "",
        user_name: str = "",
        conversation_id: str = "",
    ) -> str:
        """Generate an assistant response asynchronously."""
        try:
            return await self._generate_async_internal(
                messages,
                is_voice=is_voice,
                channel=channel,
                user_contact=user_contact,
                user_name=user_name,
                conversation_id=conversation_id,
            )
        except Exception as exc:
            print(f"[ERROR] AIService Error: {exc}")
            return "Maaf kijiye, abhi technical issue hai. Please thori der baad dobara try karein."

    def generate_response(
        self,
        messages: list[dict[str, str]],
        is_voice: bool = False,
        channel: str = "unknown",
        user_contact: str = "",
        user_name: str = "",
        conversation_id: str = "",
    ) -> str:
        """Synchronous wrapper for async response generation."""
        try:
            return asyncio.run(
                self.generate_response_async(
                    messages,
                    is_voice=is_voice,
                    channel=channel,
                    user_contact=user_contact,
                    user_name=user_name,
                    conversation_id=conversation_id,
                )
            )
        except RuntimeError:
            return "Please use async response method in running event loop contexts."


ai_service = AIService()
