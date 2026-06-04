"""
Tracking Brief router — /api/tracking-brief endpoints.

Manages client keyword tracking configurations. Default: ZEE5 demo brief.
Briefs stored in Redis with 30-day TTL.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class KeywordConfig(BaseModel):
    keyword: str
    languages: list[str] = ["english"]
    compound_filter: Optional[str] = None


class TrackingBrief(BaseModel):
    client_id: str
    client_name: str
    company_keywords: list[KeywordConfig]
    competition_keywords: list[KeywordConfig]
    industry_keywords: list[KeywordConfig]
    report_email: str
    report_time: str = "08:00"


# ── Default ZEE5 Demo Brief ───────────────────────────────────────

ZEE5_BRIEF = TrackingBrief(
    client_id="zee5",
    client_name="ZEE5 / Zee Entertainment",
    report_email="demo@veetechnologies.com",
    report_time="08:00",
    company_keywords=[
        KeywordConfig(keyword="ZEE5", languages=["english", "hindi", "tamil", "telugu", "bengali", "marathi", "malayalam", "kannada"]),
        KeywordConfig(keyword="ZEEL", languages=["english", "hindi"]),
        KeywordConfig(keyword="Raghavendra Hunsur", languages=["english"]),
        KeywordConfig(keyword="Manish Kalra", languages=["english"]),
        KeywordConfig(keyword="Nimisha Pandey", languages=["english"]),
        KeywordConfig(keyword="Nitin Mittal", languages=["english"]),
        KeywordConfig(keyword="Bhushan Kolleri", languages=["english"]),
    ],
    competition_keywords=[
        KeywordConfig(keyword="Amazon Prime Video India", languages=["english", "hindi", "tamil", "telugu", "bengali", "marathi", "malayalam", "kannada"]),
        KeywordConfig(keyword="Jio Hotstar", languages=["english", "hindi", "tamil", "telugu", "bengali", "marathi", "malayalam", "kannada"]),
        KeywordConfig(keyword="Sony LIV", languages=["english", "hindi", "tamil", "telugu", "bengali", "marathi", "malayalam", "kannada"]),
        KeywordConfig(keyword="Hoi Choi OTT", languages=["bengali"]),
        KeywordConfig(keyword="Aha OTT", languages=["tamil", "telugu"]),
        KeywordConfig(keyword="Sun Nxt", languages=["tamil"]),
        KeywordConfig(keyword="Netflix India", languages=["english", "hindi", "tamil", "telugu", "bengali", "marathi", "malayalam", "kannada"]),
    ],
    industry_keywords=[
        KeywordConfig(keyword="OTT industry India", languages=["english"]),
        KeywordConfig(keyword="OTT platforms India", languages=["english"]),
        KeywordConfig(keyword="digital streaming India", languages=["english"]),
        KeywordConfig(keyword="video streaming India", languages=["english"]),
        KeywordConfig(keyword="I&B ministry OTT", languages=["english"], compound_filter="OTT"),
        KeywordConfig(keyword="KPMG streaming", languages=["english"], compound_filter="OTT"),
        KeywordConfig(keyword="Ormax OTT", languages=["english"], compound_filter="OTT"),
    ],
)


# ── CRUD Endpoints ────────────────────────────────────────────────


@router.post("/api/tracking-brief")
async def save_brief(brief: TrackingBrief):
    """Save or update a client tracking brief."""
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            await r.set(f"brief:{brief.client_id}", brief.model_dump_json(), ex=2592000)
            await r.sadd("all_clients", brief.client_id)
    except Exception as e:
        logger.warning(f"Redis save failed: {e}")
    return {"status": "saved", "client_id": brief.client_id}


@router.get("/api/tracking-brief")
async def list_briefs():
    """List all client tracking briefs."""
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            client_ids = await r.smembers("all_clients")
            if not client_ids:
                await save_brief(ZEE5_BRIEF)
                client_ids = {"zee5"}
            briefs = []
            for cid in client_ids:
                raw = await r.get(f"brief:{cid}")
                if raw:
                    briefs.append(json.loads(raw))
            if briefs:
                return {"briefs": briefs, "count": len(briefs)}
    except Exception as e:
        logger.warning(f"Redis list failed: {e}")
    # Fallback: return ZEE5 demo
    return {"briefs": [ZEE5_BRIEF.model_dump()], "count": 1}


@router.get("/api/tracking-brief/{client_id}")
async def get_brief(client_id: str):
    """Get a specific client brief by ID."""
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            raw = await r.get(f"brief:{client_id}")
            if raw:
                return json.loads(raw)
    except Exception:
        pass
    if client_id == "zee5":
        return ZEE5_BRIEF.model_dump()
    raise HTTPException(status_code=404, detail=f"No brief for client_id: {client_id}")


@router.delete("/api/tracking-brief/{client_id}")
async def delete_brief(client_id: str):
    """Delete a client brief."""
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            await r.delete(f"brief:{client_id}")
            await r.srem("all_clients", client_id)
    except Exception as e:
        logger.warning(f"Redis delete failed: {e}")
    return {"status": "deleted", "client_id": client_id}


# ── Brief Feed Endpoint ───────────────────────────────────────────


@router.get("/api/feed/brief/{client_id}")
async def get_brief_feed(client_id: str):
    """
    Fetch all articles for all keywords in a client's tracking brief.
    Groups results by: company / competition / industry.
    """
    from services.ingestion import fetch_google_news_rss

    brief_data = await get_brief(client_id)
    if isinstance(brief_data, dict) and "detail" in brief_data:
        raise HTTPException(status_code=404, detail="Brief not found")

    # Parse brief (may come as dict from Redis or Pydantic model)
    if isinstance(brief_data, dict):
        company_kws = [KeywordConfig(**kc) if isinstance(kc, dict) else kc
                       for kc in brief_data.get("company_keywords", [])]
        competition_kws = [KeywordConfig(**kc) if isinstance(kc, dict) else kc
                           for kc in brief_data.get("competition_keywords", [])]
        industry_kws = [KeywordConfig(**kc) if isinstance(kc, dict) else kc
                        for kc in brief_data.get("industry_keywords", [])]
        client_name = brief_data.get("client_name", client_id)
    else:
        company_kws = brief_data.company_keywords
        competition_kws = brief_data.competition_keywords
        industry_kws = brief_data.industry_keywords
        client_name = brief_data.client_name

    async def fetch_category(kw_configs: list[KeywordConfig]) -> list:
        articles = []
        tasks = [fetch_google_news_rss(kc.keyword, days=5) for kc in kw_configs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for kc, result in zip(kw_configs, results):
            if isinstance(result, list):
                for a in result:
                    if kc.compound_filter:
                        combined = (a.get("title", "") + " " + a.get("body_text", "")).lower()
                        if kc.compound_filter.lower() not in combined:
                            continue
                    a["matchedKeyword"] = kc.keyword
                    articles.append(a)
        seen, unique = set(), []
        for a in articles:
            url = a.get("url", "")
            if url and url not in seen:
                seen.add(url)
                unique.append(a)
        return unique

    company, competition, industry = await asyncio.gather(
        fetch_category(company_kws),
        fetch_category(competition_kws),
        fetch_category(industry_kws),
    )

    return {
        "client_id": client_id,
        "client_name": client_name,
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
        "company": company,
        "competition": competition,
        "industry": industry,
        "total": len(company) + len(competition) + len(industry),
    }
