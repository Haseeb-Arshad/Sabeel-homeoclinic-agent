"""
Knowledge retrieval service backed by Supabase vector search.
"""

from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.db_service import db_service

logger = logging.getLogger(__name__)


class KnowledgeService:
    """Retrieve website-grounded snippets for response generation."""

    def __init__(self):
        self._client: AsyncOpenAI | None = None

    @staticmethod
    def _client_kwargs() -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        if settings.openai_default_headers:
            kwargs["default_headers"] = settings.openai_default_headers
        return kwargs

    def _openai_client(self) -> AsyncOpenAI | None:
        if not settings.openai_enabled:
            return None
        if not self._client:
            self._client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                **self._client_kwargs(),
            )
        return self._client

    async def retrieve_relevant_content(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        client = self._openai_client()
        if not query.strip() or not db_service.is_configured or client is None:
            return []

        try:
            response = await client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=query,
            )
            embedding = response.data[0].embedding
        except Exception as exc:
            logger.error("Embedding generation failed: %s", exc)
            return []

        return db_service.search_kb(embedding, match_count=top_k)

    @staticmethod
    def format_context(snippets: list[dict[str, Any]]) -> str:
        if not snippets:
            return ""

        lines: list[str] = []
        for index, item in enumerate(snippets, start=1):
            title = item.get("title") or item.get("source_title") or "Website Knowledge"
            content = str(item.get("content", "")).strip().replace("\n", " ")
            source_url = item.get("source_url") or item.get("url") or ""
            if not content:
                continue
            lines.append(f"[{index}] {title}: {content[:500]}")
            if source_url:
                lines.append(f"Source: {source_url}")

        return "\n".join(lines)


knowledge_service = KnowledgeService()
