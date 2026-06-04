"""
Article chat engine — FAISS + MiniLM for retrieval, Ollama/Qwen2.5:3b for generation.

Sessions are stored in Redis (30-min TTL). FAISS indices are kept in-memory
(keyed by session_id) since they cannot be serialized to Redis directly.
Falls back to keyword search + context extraction if models unavailable.
"""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)

CHAT_SESSION_TTL = 1800  # 30 minutes
OLLAMA_MODEL = "qwen2.5:3b"  # Always use 3b parameter model

# In-memory FAISS index store (complement to Redis session metadata)
_faiss_indexes: dict[str, dict] = {}


def _chunk_text(text: str, size: int = 256, overlap: int = 50) -> list[str]:
    """Split text into overlapping word-level chunks."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + size])
        chunks.append(chunk)
        i += size - overlap
    return chunks or [text[:500]]


# ── Redis session helpers ─────────────────────────────────────────


async def _save_session_meta(session_id: str, data: dict) -> None:
    """Save session metadata (title, chunks) to Redis."""
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            await r.setex(f"chat:{session_id}", CHAT_SESSION_TTL, json.dumps(data))
    except Exception as e:
        logger.debug(f"Redis chat save failed: {e}")


async def _get_session_meta(session_id: str) -> dict | None:
    """Retrieve session metadata from Redis."""
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            val = await r.get(f"chat:{session_id}")
            return json.loads(val) if val else None
    except Exception:
        pass
    return None


async def _delete_session_meta(session_id: str) -> None:
    """Delete session metadata from Redis."""
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            await r.delete(f"chat:{session_id}")
    except Exception:
        pass


# ── Session Lifecycle ─────────────────────────────────────────────


async def start_session(
    session_id: str, article_text: str, article_title: str
) -> None:
    """
    Create a new chat session for an article.
    Chunks the article text and builds a FAISS index for retrieval.
    Falls back to keyword-only search if FAISS/MiniLM unavailable.
    """
    chunks = _chunk_text(article_text)
    meta = {"chunks": chunks, "title": article_title}

    try:
        import faiss

        from services.ml_models import get_embed_model
        _embed_model = get_embed_model()
        if _embed_model is None:
            raise ValueError("Embedding model not loaded")

        embeddings = _embed_model.encode(chunks).astype("float32")
        index = faiss.IndexFlatL2(embeddings.shape[1])
        index.add(embeddings)

        # Store FAISS index in memory (can't serialize to Redis)
        _faiss_indexes[session_id] = {"index": index, "model": _embed_model, "embeddings": embeddings}
        logger.info("[Chat] FAISS index built for session %s (%d chunks)", session_id, len(chunks))
    except Exception as e:
        logger.error("[Chat] FAISS setup failed for session %s: %s", session_id, e)
        raise

    # Save metadata to Redis
    await _save_session_meta(session_id, meta)


async def ask_question(session_id: str, question: str) -> str:
    """
    Answer a question about an article using RAG (FAISS + Ollama qwen2.5:3b).
    Falls back to keyword search + context extraction.
    """
    # Get session metadata (from Redis or in-memory fallback)
    meta = await _get_session_meta(session_id)
    if not meta:
        return "Session not found or expired. Please reopen the article."

    chunks = meta.get("chunks", [])
    title = meta.get("title", "this article")
    faiss_data = _faiss_indexes.get(session_id)

    # ── Retrieve relevant chunks ─────────────────────────────
    context_chunks: list[str] = []

    if faiss_data and "index" in faiss_data:
        q_embed = faiss_data["model"].encode([question]).astype("float32")
        _, indices = faiss_data["index"].search(q_embed, k=min(3, len(chunks)))
        context_chunks = [chunks[i] for i in indices[0] if i < len(chunks)]
    else:
        return "RAG models unavailable for retrieval."

    context = "\n\n".join(context_chunks)

    # ── Generate answer via Ollama (qwen2.5:3b) ──────────
    prompt = f"""You are answering questions about a news article.
Article title: {title}

Relevant content from the article:
{context}

IMPORTANT RULES:
- Only answer based on the article content above
- If the answer is not in the article, say exactly:
  "This information is not in the article."
- Keep answers concise (2-3 sentences max)
- Do not use outside knowledge

Question: {question}
Answer:"""

    import os
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    ollama_model = os.getenv("OLLAMA_MODEL", OLLAMA_MODEL)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                ollama_url,
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 200},
                },
            )
            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip()
                if answer:
                    return answer
            return "Failed to generate answer from LLM."
    except Exception as e:
        logger.error(f"[Chat] Ollama call failed: {e}")
        return "LLM generation unavailable."


async def end_session(session_id: str) -> None:
    """End a chat session and free memory."""
    _faiss_indexes.pop(session_id, None)
    await _delete_session_meta(session_id)
