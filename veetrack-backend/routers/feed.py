"""
Feed router — /api/feed endpoint.

Fetches from all 5 sources via ingestion service,
runs the NLP pipeline, and returns processed articles.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from services.ingestion import fetch_all_sources, background_pre_scrape
from services.nlp_pipeline import process_articles

logger = logging.getLogger(__name__)

router = APIRouter()


class FeedRequest(BaseModel):
    keywords: list[str]
    limit: int = 20
    days: int = 5


@router.post("/api/feed")
async def get_feed(req: FeedRequest, background_tasks: BackgroundTasks):
    """Fetch and process articles from all sources."""
    raw = await fetch_all_sources(req.keywords, days=req.days)
    processed = await process_articles(raw)
    processed.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
    
    top_articles = processed[: req.limit]
    
    # Fire off background worker to silently pre-scrape the text for instant loading
    background_tasks.add_task(background_pre_scrape, top_articles)
    
    return top_articles
