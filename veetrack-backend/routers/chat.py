"""
Chat router — /api/chat endpoints.

Article chat sessions using FAISS + MiniLM for retrieval
and Ollama/Qwen for generation (with mock fallback).
Sessions are in-memory (Redis later).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from services.chat_engine import start_session, ask_question, end_session

logger = logging.getLogger(__name__)

router = APIRouter()


class StartChatRequest(BaseModel):
    article_url: str = ""
    article_text: str = ""
    article_title: str = ""


class AskRequest(BaseModel):
    session_id: str
    question: str


class EndChatRequest(BaseModel):
    session_id: str


@router.post("/api/chat")
async def start_chat(req: StartChatRequest):
    """Create a new chat session for an article."""
    import uuid

    session_id = str(uuid.uuid4())
    await start_session(session_id, req.article_text, req.article_title)
    return {"session_id": session_id}


@router.post("/api/chat/ask")
async def ask(req: AskRequest):
    """Ask a question in an existing chat session."""
    answer = await ask_question(req.session_id, req.question)
    return {"answer": answer}


@router.delete("/api/chat")
async def end_chat(session_id: str):
    """End a chat session and free memory."""
    await end_session(session_id)
    return {"status": "ended"}
