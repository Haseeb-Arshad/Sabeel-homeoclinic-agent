"""Ingest Sabeel Homeo website content into Supabase kb_chunks."""

from __future__ import annotations

import hashlib
import html
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import settings
from app.services.db_service import db_service

WP_API_BASE = os.getenv("WORDPRESS_API_BASE", "https://sabeelhomeoclinic.com/wp-json/wp/v2")


@dataclass
class SourceDoc:
    source_type: str
    source_id: str
    title: str
    url: str
    text: str


def strip_html(text: str) -> str:
    cleaned = html.unescape(text or "")
    cleaned = re.sub(r"<script\b.*?</script>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<style\b.*?</style>", " ", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"\[[^\[\]]+\]", " ", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"(?:%[0-9A-Fa-f]{2}){3,}", " ", cleaned)
    cleaned = re.sub(r"\b[A-Za-z0-9+/=_%-]{60,}\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(end - overlap, 0)
    return chunks


def fetch_collection(endpoint: str, per_page: int = 50, max_pages: int = 20) -> Iterable[dict]:
    for page in range(1, max_pages + 1):
        response = requests.get(
            f"{WP_API_BASE}/{endpoint}",
            params={"per_page": per_page, "page": page},
            timeout=30,
        )
        if response.status_code == 400:
            break
        response.raise_for_status()
        items = response.json()
        if not items:
            break
        for item in items:
            yield item


def load_docs() -> list[SourceDoc]:
    docs: list[SourceDoc] = []

    for post in fetch_collection("posts"):
        title = strip_html(post.get("title", {}).get("rendered", ""))
        content = strip_html(post.get("content", {}).get("rendered", ""))
        if content:
            docs.append(
                SourceDoc(
                    source_type="post",
                    source_id=str(post.get("id", "")),
                    title=title or "Article",
                    url=post.get("link", ""),
                    text=content,
                )
            )

    for page in fetch_collection("pages"):
        title = strip_html(page.get("title", {}).get("rendered", ""))
        content = strip_html(page.get("content", {}).get("rendered", ""))
        if content:
            docs.append(
                SourceDoc(
                    source_type="page",
                    source_id=str(page.get("id", "")),
                    title=title or "Page",
                    url=page.get("link", ""),
                    text=content,
                )
            )

    return docs


def build_rows(docs: list[SourceDoc]) -> list[dict]:
    client_kwargs: dict[str, object] = {}
    if settings.openai_base_url:
        client_kwargs["base_url"] = settings.openai_base_url
    if settings.openai_default_headers:
        client_kwargs["default_headers"] = settings.openai_default_headers

    client = OpenAI(api_key=settings.OPENAI_API_KEY, **client_kwargs)
    rows: list[dict] = []

    for doc in docs:
        chunks = chunk_text(doc.text)
        if not chunks:
            continue

        embeddings = client.embeddings.create(
            model=settings.OPENAI_EMBEDDING_MODEL,
            input=chunks,
        )

        for index, item in enumerate(embeddings.data):
            content = chunks[index]
            hash_id = hashlib.sha1(f"{doc.source_type}:{doc.source_id}:{index}".encode("utf-8")).hexdigest()
            rows.append(
                {
                    "id": hash_id,
                    "source_type": "wordpress",
                    "source_id": f"{doc.source_type}:{doc.source_id}",
                    "source_url": doc.url,
                    "source_title": doc.title,
                    "content": content,
                    "metadata": {"chunk_index": index},
                    "embedding": item.embedding,
                }
            )

    return rows


def main() -> None:
    if not db_service.is_configured:
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and key env vars.")

    docs = load_docs()
    rows = build_rows(docs)
    inserted = db_service.upsert_knowledge_chunks(rows)
    print(f"Loaded docs: {len(docs)}")
    print(f"Upserted chunks: {inserted}")


if __name__ == "__main__":
    main()
