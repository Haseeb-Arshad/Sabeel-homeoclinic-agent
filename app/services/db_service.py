"""
Database service for Supabase-backed storage.
Handles conversations, messages, appointments, and knowledge retrieval.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from threading import RLock
from typing import Any
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover - optional dependency in some environments
    Client = Any  # type: ignore[assignment]
    create_client = None  # type: ignore[assignment]


MessagePayload = dict[str, str]


class DatabaseService:
    """Thin wrapper around Supabase tables and RPCs with local fallback storage."""

    def __init__(self):
        self._client: Client | None = None
        self._lock = RLock()
        self._local_conversations: dict[str, dict[str, Any]] = {}
        self._local_messages: list[dict[str, Any]] = []
        self._local_appointments: dict[str, dict[str, Any]] = {}

    @property
    def is_configured(self) -> bool:
        return bool(settings.SUPABASE_URL and self._supabase_key and create_client)

    @property
    def _supabase_key(self) -> str:
        return settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY

    def client(self) -> Client | None:
        if self._client:
            return self._client

        if not self.is_configured:
            return None

        try:
            self._client = create_client(settings.SUPABASE_URL, self._supabase_key)
            return self._client
        except Exception as exc:
            logger.error("Failed to initialize Supabase client: %s", exc)
            return None

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    @staticmethod
    def _new_local_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"

    def _store_local_conversation(
        self,
        conversation_id: str,
        channel: str,
        external_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            existing = self._local_conversations.get(conversation_id, {})
            merged_metadata = {**existing.get("metadata", {}), **(metadata or {})}
            self._local_conversations[conversation_id] = {
                "id": conversation_id,
                "channel": channel,
                "external_id": external_id or existing.get("external_id", ""),
                "metadata": merged_metadata,
                "created_at": existing.get("created_at", self._now_iso()),
                "updated_at": self._now_iso(),
            }

    def _find_local_conversation(self, channel: str, external_id: str) -> str | None:
        with self._lock:
            matches = [
                conversation
                for conversation in self._local_conversations.values()
                if conversation.get("channel") == channel and conversation.get("external_id") == external_id
            ]
        if not matches:
            return None
        matches.sort(key=lambda item: item.get("updated_at", item.get("created_at", "")), reverse=True)
        return str(matches[0]["id"])

    def get_or_create_conversation(
        self,
        channel: str,
        external_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Reuse an existing conversation for the same channel/external ID when possible."""
        if not external_id:
            return self.create_conversation(channel=channel, external_id="", metadata=metadata)

        local_id = self._find_local_conversation(channel, external_id)
        if local_id:
            self._store_local_conversation(local_id, channel, external_id, metadata)
            return local_id

        client = self.client()
        if client:
            try:
                response = (
                    client.table("conversations")
                    .select("id")
                    .eq("channel", channel)
                    .eq("external_id", external_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                data = response.data or []
                if data and data[0].get("id"):
                    conversation_id = str(data[0]["id"])
                    self._store_local_conversation(conversation_id, channel, external_id, metadata)
                    return conversation_id
            except Exception as exc:
                logger.error("Failed to fetch existing conversation: %s", exc)

        return self.create_conversation(channel=channel, external_id=external_id, metadata=metadata)

    def create_conversation(
        self,
        channel: str,
        external_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Create a conversation and return conversation ID."""
        fallback_id = self._new_local_id("local")

        client = self.client()
        if client:
            payload = {
                "channel": channel,
                "external_id": external_id or None,
                "metadata": metadata or {},
            }
            try:
                response = client.table("conversations").insert(payload).execute()
                data = response.data or []
                if data and data[0].get("id"):
                    conversation_id = str(data[0]["id"])
                    self._store_local_conversation(conversation_id, channel, external_id, metadata)
                    return conversation_id
            except Exception as exc:
                logger.error("Failed to create conversation: %s", exc)

        self._store_local_conversation(fallback_id, channel, external_id, metadata)
        return fallback_id

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist a conversation message."""
        record = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "created_at": self._now_iso(),
        }

        with self._lock:
            self._local_messages.append(record)

        client = self.client()
        if not client:
            return

        try:
            client.table("messages").insert(record).execute()
        except Exception as exc:
            logger.error("Failed to add message: %s", exc)

    def get_recent_messages(self, conversation_id: str, limit: int = 20) -> list[MessagePayload]:
        """Return recent conversation messages in chronological order."""
        client = self.client()
        if client:
            try:
                response = (
                    client.table("messages")
                    .select("role,content,created_at")
                    .eq("conversation_id", conversation_id)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                data = list(reversed(response.data or []))
                if data:
                    return [
                        {"role": str(item["role"]), "content": str(item["content"])}
                        for item in data
                        if item.get("role") and item.get("content")
                    ]
            except Exception as exc:
                logger.error("Failed to fetch conversation messages: %s", exc)

        with self._lock:
            items = [
                {"role": str(item["role"]), "content": str(item["content"])}
                for item in self._local_messages
                if item.get("conversation_id") == conversation_id
            ]
        return items[-limit:]

    def build_conversation_messages(
        self,
        conversation_id: str,
        latest_user_message: str,
        limit: int = 20,
    ) -> list[MessagePayload]:
        messages = self.get_recent_messages(conversation_id, limit=limit)
        if latest_user_message.strip():
            messages.append({"role": "user", "content": latest_user_message})
        return messages

    def create_appointment_request(self, payload: dict[str, Any]) -> str:
        """Create a pending appointment request and return appointment ID."""
        fallback_id = self._new_local_id("appt")

        payload = {
            "status": "pending",
            **payload,
        }

        client = self.client()
        if client:
            try:
                response = client.table("appointments").insert(payload).execute()
                data = response.data or []
                if data and data[0].get("id"):
                    appointment_id = str(data[0]["id"])
                    with self._lock:
                        self._local_appointments[appointment_id] = {"id": appointment_id, **payload}
                    return appointment_id
            except Exception as exc:
                logger.error("Failed to create appointment request: %s", exc)

        with self._lock:
            self._local_appointments[fallback_id] = {"id": fallback_id, **payload}
        return fallback_id

    def search_kb(self, embedding: list[float], match_count: int = 5) -> list[dict[str, Any]]:
        """Run vector similarity search through a Supabase RPC function."""
        client = self.client()
        if not client:
            return []

        try:
            response = client.rpc(
                "match_kb_chunks",
                {
                    "query_embedding": embedding,
                    "match_count": match_count,
                },
            ).execute()
            return response.data or []
        except Exception as exc:
            logger.error("Knowledge search failed: %s", exc)
            return []

    def upsert_knowledge_chunks(self, rows: list[dict[str, Any]]) -> int:
        """Upsert knowledge chunks into kb_chunks table."""
        if not rows:
            return 0

        client = self.client()
        if not client:
            return 0

        try:
            client.table("kb_chunks").upsert(rows).execute()
            return len(rows)
        except Exception as exc:
            logger.error("Failed to upsert knowledge chunks: %s", exc)
            return 0


db_service = DatabaseService()
