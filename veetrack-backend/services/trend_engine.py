"""
Trend engine — real-time trend scoring using Redis time series + scipy zscore.

Stores per-keyword hourly article counts in Redis with 8-day TTL.
Falls back to simple arithmetic if Redis/scipy unavailable.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# In-memory fallback when Redis is unavailable
_keyword_history: dict[str, list[dict]] = defaultdict(list)

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# ── Redis-backed functions ────────────────────────────────────────


async def record_keyword_volume(keyword: str, count: int) -> None:
    """Store hourly article count in Redis. TTL 8 days."""
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            hour_key = f"vol:{keyword}:{datetime.utcnow().strftime('%Y-%m-%d-%H')}"
            await r.setex(hour_key, 691200, str(count))  # 8 days TTL
            return
    except Exception as e:
        logger.debug(f"Redis record_keyword_volume failed: {e}")
    # In-memory fallback
    _keyword_history[keyword].append({
        "timestamp": datetime.now(timezone.utc),
        "count": count,
        "avg_sentiment": 0.5,
    })
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    _keyword_history[keyword] = [
        r for r in _keyword_history[keyword] if r["timestamp"] > cutoff
    ]


async def get_hourly_volume(keyword: str) -> list[int]:
    """Returns list of 24 ints (last 24 hours, oldest first). Returns [0]*24 if no data."""
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            now = datetime.utcnow()
            volumes = []
            for h in range(23, -1, -1):
                hour = now - timedelta(hours=h)
                key = f"vol:{keyword}:{hour.strftime('%Y-%m-%d-%H')}"
                val = await r.get(key)
                volumes.append(int(val) if val else 0)
            return volumes
    except Exception as e:
        logger.debug(f"Redis get_hourly_volume failed: {e}")
    return [0] * 24


async def compute_trend_score(keyword: str, current_count: int) -> int:
    """
    Z-score based trend score 0-100.
    Uses Redis 7-day history if available, falls back to in-memory.
    """
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            now = datetime.utcnow()
            history = []
            for d in range(1, 8):
                for h in range(24):
                    t = now - timedelta(days=d, hours=h)
                    val = await r.get(f"vol:{keyword}:{t.strftime('%Y-%m-%d-%H')}")
                    if val:
                        history.append(int(val))
            if not history or len(history) < 5:
                return min(50, current_count * 5)
            if HAS_NUMPY:
                mean = np.mean(history)
                std = np.std(history)
                if std == 0:
                    return 30
                z = (current_count - mean) / std
                if z >= 3:
                    return 95
                if z >= 2:
                    return 80
                if z >= 1:
                    return 60
                if z >= 0:
                    return 40
                return 20
            else:
                mean_count = sum(history) / len(history)
                return min(100, int((current_count / (mean_count + 1)) * 40))
    except Exception as e:
        logger.debug(f"Redis compute_trend_score failed: {e}")
    # In-memory fallback
    history = _keyword_history.get(keyword, [])
    if len(history) < 3:
        return 30
    counts = [r["count"] for r in history]
    mean_count = sum(counts) / len(counts)
    return min(100, int((current_count / (mean_count + 1)) * 40))


async def get_prev_sentiment(keyword: str) -> str:
    """Get previous batch majority sentiment from Redis."""
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            val = await r.get(f"sent:{keyword}:prev")
            return val or "neutral"
    except Exception:
        pass
    return "neutral"


async def store_sentiment(keyword: str, sentiment: str) -> None:
    """Store current sentiment for next comparison. TTL 2 hours."""
    try:
        from core.cache_client import get_cache
        r = await get_cache()
        if r:
            await r.setex(f"sent:{keyword}:prev", 7200, sentiment)
    except Exception:
        pass


# ── Legacy sync helpers (used by nlp_pipeline deterministic scoring) ─


def compute_trend_score_deterministic(url: str, keyword: str) -> int:
    """
    Deterministic 0-100 trend score for a single article.
    Used by nlp_pipeline when we don't want to await async.
    """
    import hashlib
    h = int(hashlib.md5((url + keyword).encode()).hexdigest(), 16)
    return 10 + (h % 81)


def record_ingestion(keyword: str, article_count: int, avg_sentiment_score: float) -> None:
    """Sync in-memory record for legacy callers."""
    _keyword_history[keyword].append({
        "timestamp": datetime.now(timezone.utc),
        "count": article_count,
        "avg_sentiment": avg_sentiment_score,
    })
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    _keyword_history[keyword] = [
        r for r in _keyword_history[keyword] if r["timestamp"] > cutoff
    ]


def get_keyword_history(keyword: str) -> list[dict]:
    """Return ingestion history for a keyword (in-memory fallback)."""
    return _keyword_history.get(keyword, [])


def get_all_keywords() -> list[str]:
    """Return all keywords with recorded history."""
    return list(_keyword_history.keys())
