"""
Alert engine — REAL threshold-based alerts. No mock/random data.

Evaluates 5 signal types:
  1. Volume spike (3x above baseline)
  2. Sentiment reversal (positive→negative)
  3. PR risk (negative keyword in major outlet)
  4. Trend emerging (score crosses 60)
  5. New source coverage (brand new outlet detected)

Publishes all fired alerts to Redis pub/sub → SSE endpoint streams to browser.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)

NEGATIVE_WORDS = [
    "controversy", "lawsuit", "banned", "fine", "penalty", "complaint",
    "scam", "fraud", "crisis", "shutdown", "violation", "illegal",
    "arrested", "probe", "investigation", "cybercrime", "hack", "breach",
    "exposed", "scandal", "allegation", "accused", "defamation", "sued",
    "insider trading", "charges", "indicted", "convicted",
]

MAJOR_OUTLETS = [
    "economictimes", "thehindu", "hindustantimes", "ndtv", "livemint",
    "businessstandard", "financialexpress", "moneycontrol", "timesofindia",
    "reuters", "bloomberg", "indianexpress", "telegraphindia", "fortune",
    "techcrunch", "wired", "bbc", "guardian", "wsj", "nytimes",
]


def _build_alert(
    alert_type: str,
    priority: str,
    keyword: str,
    message: str,
    score: int,
    threshold: int,
    extra: dict | None = None,
) -> dict:
    alert = {
        "id": str(uuid4()),
        "type": alert_type,
        "priority": priority,
        "keyword": keyword,
        "message": message,
        "score": score,
        "threshold": threshold,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if extra:
        alert.update(extra)
    return alert


async def evaluate_real_thresholds(keyword: str, articles: list) -> list[dict]:
    """
    Evaluate REAL alert thresholds against fetched articles.
    No random data. No mock templates. Pure signal-based.
    """
    alerts: list[dict] = []

    try:
        from core.cache_client import get_cache
        r = await get_cache()
    except Exception:
        r = None

    # ── THRESHOLD 1: Volume Spike ─────────────────────────────
    try:
        from services.trend_engine import get_hourly_volume
        volumes = await get_hourly_volume(keyword)
        current = len(articles)
        past_avg = sum(volumes[:-1]) / max(len(volumes[:-1]), 1)
        if past_avg > 0 and current > past_avg * 3:
            alerts.append(_build_alert(
                "volume_spike", "high", keyword,
                f"'{keyword}' has {current} articles — {current / past_avg:.1f}x above average.",
                score=current, threshold=int(past_avg * 3),
            ))
    except Exception as e:
        logger.debug(f"Volume spike check failed: {e}")

    # ── THRESHOLD 2: Sentiment Reversal ──────────────────────
    try:
        from services.trend_engine import get_prev_sentiment, store_sentiment
        prev_sent = await get_prev_sentiment(keyword)
        sentiments = [
            a.get("sentiment", "neutral") if isinstance(a, dict) else "neutral"
            for a in articles
        ]
        if sentiments:
            curr_sent = Counter(sentiments).most_common(1)[0][0]
            await store_sentiment(keyword, curr_sent)
            if prev_sent == "positive" and curr_sent == "negative":
                alerts.append(_build_alert(
                    "sentiment_reversal", "high", keyword,
                    f"Coverage sentiment for '{keyword}' reversed from positive to negative.",
                    score=0, threshold=0,
                ))
    except Exception as e:
        logger.debug(f"Sentiment reversal check failed: {e}")

    # ── THRESHOLD 3: PR Risk ──────────────────────────────────
    for article in articles:
        url = (article.get("url", "") if isinstance(article, dict) else "").lower()
        headline = (article.get("title", article.get("headline", "")) if isinstance(article, dict) else "").lower()
        is_major = any(outlet in url for outlet in MAJOR_OUTLETS)
        has_negative = any(word in headline for word in NEGATIVE_WORDS)
        if is_major and has_negative:
            alerts.append(_build_alert(
                "pr_risk", "critical", keyword,
                f"Negative coverage in major outlet: {article.get('source', '')} — {headline[:80]}",
                score=85, threshold=70,
                extra={"articleUrl": article.get("url", "")},
            ))
            break  # One PR risk alert per batch

    # ── THRESHOLD 4: Trend Emerging ───────────────────────────
    try:
        from services.trend_engine import compute_trend_score
        trend = await compute_trend_score(keyword, len(articles))
        prev_trend = 0
        if r:
            prev_trend_raw = await r.get(f"trend:{keyword}:prev")
            prev_trend = int(prev_trend_raw) if prev_trend_raw else 0
            await r.set(f"trend:{keyword}:prev", str(trend), ex=86400)
        if trend > 60 and prev_trend < 30:
            alerts.append(_build_alert(
                "trend_emerging", "medium", keyword,
                f"'{keyword}' is now trending at score {trend} (was {prev_trend}).",
                score=trend, threshold=60,
            ))
    except Exception as e:
        logger.debug(f"Trend emerging check failed: {e}")

    # ── THRESHOLD 5: New Source Coverage ─────────────────────
    try:
        if r:
            prev_sources_raw = await r.get(f"sources:{keyword}")
            prev_sources = set(json.loads(prev_sources_raw)) if prev_sources_raw else set()
            curr_sources = set(
                a.get("source", "") for a in articles
                if isinstance(a, dict) and a.get("source")
            )
            new_sources = curr_sources - prev_sources
            if new_sources and prev_sources:
                alerts.append(_build_alert(
                    "new_source", "low", keyword,
                    f"'{keyword}' now covered by: {', '.join(list(new_sources)[:3])}",
                    score=len(new_sources), threshold=1,
                ))
            if curr_sources:
                await r.set(f"sources:{keyword}", json.dumps(list(curr_sources)), ex=604800)
    except Exception as e:
        logger.debug(f"New source check failed: {e}")

    # ── Publish to Redis pub/sub ──────────────────────────────
    if r and alerts:
        for alert in alerts:
            try:
                await r.publish("veetrack:alerts", json.dumps(alert))
            except Exception:
                pass

    return alerts
