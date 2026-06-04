"""Alert evaluation Celery task — runs real threshold checks every 15 minutes."""
from __future__ import annotations
import asyncio
import json
import logging

logger = logging.getLogger(__name__)

try:
    from celery_app import app
    from core.cache_client import get_sync_cache

    redis_sync = get_sync_cache()

    @app.task
    def evaluate_all_keywords():
        """Run alert threshold evaluation for all active keywords."""
        if not redis_sync:
            return {"keywords_checked": 0, "alerts_fired": 0}
        keywords = redis_sync.smembers("active_keywords") or set()
        fired = 0
        for kw in keywords:
            kw = kw if isinstance(kw, str) else kw.decode()
            cached = redis_sync.get(f"feed:{kw.lower().replace(' ', '_')}")
            if cached:
                try:
                    from services.alert_engine import evaluate_real_thresholds
                    articles = json.loads(cached)
                    alerts = asyncio.run(evaluate_real_thresholds(kw, articles))
                    fired += len(alerts)
                except Exception as e:
                    logger.warning(f"Alert eval failed for {kw}: {e}")
        return {"keywords_checked": len(keywords), "alerts_fired": fired}

except ImportError as e:
    logger.warning(f"Celery not available: {e}. Alert tasks disabled.")
