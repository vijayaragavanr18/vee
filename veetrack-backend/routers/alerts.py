"""
Alerts router — /api/alerts SSE endpoint.

Subscribes to Redis pub/sub 'veetrack:alerts' channel.
Falls back to polling-based evaluation if Redis unavailable.
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/alerts")
async def stream_alerts(request: Request, keywords: str = ""):
    """
    SSE endpoint. Subscribes to Redis pub/sub 'veetrack:alerts'.
    Falls back to direct polling if Redis unavailable.
    """
    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]

    async def redis_event_generator():
        """Stream alerts from Redis pub/sub."""
        try:
            from core.cache_client import get_cache
            r = await get_cache()
            if not r:
                raise RuntimeError("Redis unavailable")
            pubsub = r.pubsub()
            await pubsub.subscribe("veetrack:alerts")
            yield 'data: {"type":"connected","message":"Alert stream ready (Redis)"}\n\n'
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                        timeout=30.0,
                    )
                    if message and message.get("type") == "message":
                        yield f"data: {message['data']}\n\n"
                    else:
                        yield ": heartbeat\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            return
        except Exception as e:
            logger.warning(f"Redis SSE failed, switching to polling: {e}")
            async for event in polling_event_generator():
                yield event

    async def polling_event_generator():
        """Fallback: poll ingestion + alert engine every 30 seconds."""
        from services.ingestion import fetch_all_sources
        from services.nlp_pipeline import process_articles
        from services.alert_engine import evaluate_real_thresholds

        yield 'data: {"type":"connected","message":"Alert stream ready (polling)"}\n\n'
        while True:
            if await request.is_disconnected():
                break
            try:
                if keyword_list:
                    articles = await fetch_all_sources(keyword_list, days=1)
                    processed = await process_articles(articles)
                    all_alerts = []
                    for kw in keyword_list:
                        kw_articles = [a for a in processed if a.get("keyword") == kw]
                        all_alerts.extend(await evaluate_real_thresholds(kw, kw_articles))
                    if all_alerts:
                        for alert in all_alerts[:5]:
                            yield f"data: {json.dumps(alert)}\n\n"
                    else:
                        yield ': heartbeat\n\n'
                else:
                    yield ': heartbeat\n\n'
            except Exception as e:
                yield f'data: {{"type":"error","message":"{str(e)}"}}\n\n'
            await asyncio.sleep(30)

    return StreamingResponse(
        redis_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
