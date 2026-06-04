"""Ingestion Celery tasks — fetch and NLP-enrich articles per keyword."""
from __future__ import annotations
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

try:
    from celery_app import app
    from services.ingestion import fetch_all_sources
    from services.nlp_pipeline import process_articles
    from services.trend_engine import record_keyword_volume
    from core.cache_client import get_sync_cache

    redis_sync = get_sync_cache()

    @app.task(bind=True, max_retries=3, default_retry_delay=60)
    def process_keyword(self, keyword: str):
        """Fetch + NLP enrich articles for one keyword. Store in Redis."""
        try:
            articles = asyncio.run(fetch_all_sources([keyword], days=1))
            enriched = asyncio.run(process_articles(articles)) if articles else []
            cache_key = f"feed:{keyword.lower().replace(' ', '_')}"
            if redis_sync:
                redis_sync.setex(cache_key, 1800, json.dumps(enriched))
                redis_sync.sadd("active_keywords", keyword)
                redis_sync.expire("active_keywords", 86400)
            asyncio.run(record_keyword_volume(keyword, len(enriched)))
            return {"keyword": keyword, "count": len(enriched)}
        except Exception as exc:
            raise self.retry(exc=exc)

    @app.task
    def process_all_active_keywords():
        """Process all keywords searched in last 24 hours."""
        if not redis_sync:
            return {"processed": 0}
        keywords = redis_sync.smembers("active_keywords") or set()
        for kw in keywords:
            kw = kw if isinstance(kw, str) else kw.decode()
            process_keyword.delay(kw)
        return {"processed": len(keywords)}

except ImportError as e:
    logger.warning(f"Celery not available: {e}. Ingestion tasks disabled.")
