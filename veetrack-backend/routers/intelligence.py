"""
Intelligence router — /api/intelligence endpoint.

Produces a standardized intelligence report shape that matches
the frontend IntelligenceReport TypeScript interface exactly.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from services.ingestion import fetch_all_sources
from services.nlp_pipeline import process_articles

logger = logging.getLogger(__name__)

router = APIRouter()


class IntelligenceRequest(BaseModel):
    keywords: list[str]
    days: int = 5


def _determine_risk_level(avg_risk: float) -> str:
    if avg_risk >= 70:
        return "critical"
    elif avg_risk >= 50:
        return "high"
    elif avg_risk >= 30:
        return "medium"
    return "low"


async def _generate_executive_brief_llm(client_name: str, keyword: str, articles: list) -> dict:
    if not articles:
        return {
            "happened": f'No significant coverage found for "{keyword}".',
            "whyItMatters": "Low media presence.",
            "recommendedAction": "Consider proactive content seeding.",
            "riskLevel": "LOW",
        }

    context = "\n".join([f"- {a.get('title', '')}: {a.get('body_text', '')[:200]}" for a in articles[:10]])
    
    prompt = f"""You are a Lead Intelligence Director at a top-tier media monitoring firm.
Analyze these {len(articles)} recent news articles about "{keyword}".

ARTICLES:
{context}

Write a highly professional, board-ready executive brief in this EXACT format — 3 bullets only:

WHAT HAPPENED: [one sentence — a highly professional synthesis of the key factual event]
WHY IT MATTERS: [one sentence — the strategic business and market impact for the client]
RECOMMENDED ACTION: [one sentence — a strategic, actionable PR/Comms directive]
RISK LEVEL: [LOW / MEDIUM / HIGH / CRITICAL]

No other text. No preamble. Just the 4 lines above."""

    import os
    import httpx

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")

    result = {
        "happened": "Analysis unavailable.",
        "whyItMatters": "Analysis unavailable.",
        "recommendedAction": "Routine monitoring.",
        "riskLevel": "LOW",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                ollama_url,
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 300},
                },
            )
            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip()
                # Robust parsing (case insensitive)
                for line in answer.split("\n"):
                    line = line.strip()
                    upper_line = line.upper()
                    if "WHAT HAPPENED:" in upper_line:
                        result["happened"] = line.split(":", 1)[1].strip().strip("*").strip()
                    elif "WHY IT MATTERS:" in upper_line:
                        result["whyItMatters"] = line.split(":", 1)[1].strip().strip("*").strip()
                    elif "RECOMMENDED ACTION:" in upper_line:
                        result["recommendedAction"] = line.split(":", 1)[1].strip().strip("*").strip()
                    elif "RISK LEVEL:" in upper_line:
                        result["riskLevel"] = line.split(":", 1)[1].strip().strip("*").strip()
                
                # Fallback if the LLM didn't use the prefixes properly but generated text
                if result["happened"] == "Analysis unavailable." and len(answer) > 50:
                    result["happened"] = answer[:200] + "..."
            else:
                logger.error(f"Ollama returned {resp.status_code}")
    except Exception as e:
        logger.error(f"Ollama executive brief failed: {type(e).__name__} - {e}")

    return result


async def _generate_article_analysis_llm(article: dict) -> dict:
    import os
    import httpx
    
    title = article.get("title", "")
    content = article.get("body_text", "")
    if not content or len(content) < 50:
        content = article.get("summary", title)
        
    prompt = f"""You are a Senior Corporate Intelligence Analyst at an elite PR tracking firm. 
Provide a master-level, highly elaborate analysis of the following article. Your analysis must be comprehensive enough to fill a full-page executive report.

ARTICLE: {title}
{content[:2000]}

Write exactly three detailed sections. Make each section an extremely comprehensive, multi-sentence paragraph (at least 5-7 long sentences) packed with strategic insights, market context, and corporate intelligence. Use a highly professional, authoritative tone.

Format your response exactly like this:

WHAT HAPPENED:
[Extremely elaborate paragraph detailing the core events, background context, key players, and specific facts mentioned in the article.]

WHY IT MATTERS:
[Extremely elaborate paragraph explaining the strategic business impact, market consequences, brand reputation implications, and deep industry consequences.]

AI NARRATIVE:
[A rich, storytelling-style cognitive POV narrative that connects this event to broader industry trends, historical context, and gives a comprehensive, immersive summary of the strategic landscape.]
"""

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")

    result = {
        "whatHappened": "",
        "whyItMatters": "",
        "aiNarrative": ""
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                ollama_url,
                json={
                    "model": ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.5, "num_predict": 1200},
                },
            )
            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip()
                import re
                
                wh_match = re.search(r'WHAT HAPPENED:(.*?)(?=WHY IT MATTERS:|$)', answer, re.DOTALL | re.IGNORECASE)
                wm_match = re.search(r'WHY IT MATTERS:(.*?)(?=AI NARRATIVE:|$)', answer, re.DOTALL | re.IGNORECASE)
                an_match = re.search(r'AI NARRATIVE:(.*?)$', answer, re.DOTALL | re.IGNORECASE)
                
                if wh_match: result["whatHappened"] = wh_match.group(1).strip().strip("*")
                if wm_match: result["whyItMatters"] = wm_match.group(1).strip().strip("*")
                if an_match: result["aiNarrative"] = an_match.group(1).strip().strip("*")
                
                # Fallback if markdown or weird formatting was used
                if not result["whatHappened"] and len(answer) > 100:
                    parts = answer.split('\n\n')
                    if len(parts) >= 3:
                        result["whatHappened"] = parts[0]
                        result["whyItMatters"] = parts[1]
                        result["aiNarrative"] = parts[2]
            else:
                logger.error(f"Ollama returned {resp.status_code}")
    except Exception as e:
        logger.error(f"Ollama article analysis failed: {type(e).__name__} - {e}")

    return result

@router.post("/api/intelligence")
async def get_intelligence(req: IntelligenceRequest):
    """
    Generate a full intelligence report.

    Returns the standardized shape:
    {
      keyword, generatedAt, pipeline,
      report: { summary, keyFindings, suggestedAction, riskLevel, whyItMatters,
                executiveBrief, topEntities, sentimentBreakdown, riskScore,
                trendScore, hourlyVolume, totalArticles, sourceCount, sources },
      articles: [...]
    }
    """
    raw = await fetch_all_sources(req.keywords, days=req.days)
    articles = await process_articles(raw)

    keyword = req.keywords[0] if req.keywords else ""

    # ── Statistics ────────────────────────────────────────────
    by_source: dict[str, int] = {}
    for a in articles:
        src = a.get("source", a.get("origin", "unknown"))
        by_source[src] = by_source.get(src, 0) + 1

    def _get_sentiment(a):
        s = a.get("sentiment", "neutral")
        return s.get("label", "neutral") if isinstance(s, dict) else s

    sent_counts = Counter(_get_sentiment(a) for a in articles)
    dominant = (
        "positive" if sent_counts.get("positive", 0) > sent_counts.get("negative", 0)
        and sent_counts.get("positive", 0) > sent_counts.get("neutral", 0)
        else "negative" if sent_counts.get("negative", 0) > sent_counts.get("neutral", 0)
        else "neutral"
    )

    # Top entities with type
    entity_counter: Counter = Counter()
    entity_type_map: dict[str, str] = {}
    for a in articles:
        for e in a.get("entities", []):
            text = e.get("text", "")
            label = e.get("label", "Topic")
            type_map = {"ORG": "Organization", "PERSON": "Person", "GPE": "Location"}
            entity_counter[text] += 1
            entity_type_map[text] = type_map.get(label, "Topic")

    top_entities = [
        {"text": text, "type": entity_type_map.get(text, "Topic"), "count": count}
        for text, count in entity_counter.most_common(10)
        if text
    ]

    avg_risk = (
        sum(a.get("risk_score", 0) for a in articles) / len(articles)
        if articles else 0
    )
    avg_trend = (
        sum(a.get("trend_score", 0) for a in articles) / len(articles)
        if articles else 0
    )
    risk_level = _determine_risk_level(avg_risk)
    source_count = len(by_source)

    # Key findings from top articles
    key_findings = [
        a.get("why_it_matters", a.get("title", ""))
        for a in articles[:5] if a.get("title")
    ]

    # Executive brief
    llm_brief = await _generate_executive_brief_llm(keyword, keyword, articles)
    
    # Deep LLM Analysis for top articles (Sequential to avoid overloading Ollama GPU)
    top_articles = articles[:10] # Limit to top 10
    for a in top_articles:
        ans = await _generate_article_analysis_llm(a)
        if isinstance(ans, dict):
            a["llm_what_happened"] = ans.get("whatHappened", "")
            a["llm_why_it_matters"] = ans.get("whyItMatters", "")
            a["llm_ai_narrative"] = ans.get("aiNarrative", "")

    # Helper to map backend article to frontend ScoredArticle shape
    def map_to_scored_article(a: dict, section: str = "company") -> dict:
        sentiment_data = a.get("sentiment", {})
        if isinstance(sentiment_data, dict):
            sentiment_label = sentiment_data.get("label", "neutral")
            sentiment_conf = sentiment_data.get("score", 0.5)
        else:
            sentiment_label = "neutral"
            sentiment_conf = 0.5

        raw_entities = a.get("entities", [])
        people = [e["text"] for e in raw_entities if isinstance(e, dict) and e.get("type") in ("PERSON", "Person")]
        orgs = [e["text"] for e in raw_entities if isinstance(e, dict) and e.get("type") in ("ORG", "Organization", "Unknown")]
        locs = [e["text"] for e in raw_entities if isinstance(e, dict) and e.get("type") in ("GPE", "Location")]

        return {
            "headline": a.get("title", a.get("headline", "Untitled")),
            "url": a.get("url", ""),
            "snippet": a.get("summary", ""),
            "fullContent": a.get("body_text", ""),
            "publication": a.get("source", a.get("origin", "Unknown")),
            "edition": "Online",
            "date": a.get("published_at", a.get("timestamp", "")),
            "section": section,
            "sentiment": sentiment_label,
            "sentimentConfidence": sentiment_conf,
            "sentimentReason": "",
            "entities": {
                "people": people,
                "organizations": orgs,
                "locations": locs
            },
            "sarcasmFlag": False,
            "sarcasmReason": "",
            "businessImpact": a.get("why_it_matters", a.get("whyItMatters", "")),
            "llm_what_happened": a.get("llm_what_happened", ""),
            "llm_why_it_matters": a.get("llm_why_it_matters", ""),
            "llm_ai_narrative": a.get("llm_ai_narrative", ""),
            "tone": "Informative",
            "keyQuote": "",
            "relevanceScore": a.get("risk_score", a.get("riskScore", 0)),
            "relevanceExplanation": a.get("suggested_action", a.get("suggestedAction", "")),
            "isPriority": a.get("trend_score", a.get("trendScore", 0)) >= 60
        }

    scored_articles = [map_to_scored_article(a) for a in articles]

    # Hourly volume from trend engine (or zeros if Redis unavailable)
    try:
        from services.trend_engine import get_hourly_volume, record_keyword_volume
        hourly_volume = await get_hourly_volume(keyword)
        await record_keyword_volume(keyword, len(articles))
    except Exception:
        hourly_volume = [0] * 24

    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "clientName": keyword,
        "criticalAlerts": [a for a in scored_articles if a.get("relevanceScore", 0) >= 70],
        "priorityItems": [a for a in scored_articles if a.get("isPriority") and a.get("relevanceScore", 0) < 70],
        "companyNews": scored_articles,
        "competitionNews": [],
        "industryNews": [],
        "executiveBrief": {
            "happened": llm_brief.get("happened", ""),
            "whyItMatters": llm_brief.get("whyItMatters", ""),
            "recommendedAction": llm_brief.get("recommendedAction", ""),
            "trendOutlook": "Stable"
        },
        "stats": {
            "totalFound": len(raw) if 'raw' in locals() else len(articles),
            "afterRelevance": len(articles),
            "critical": len([a for a in articles if a.get("risk_score", 0) >= 70]),
            "priority": len([a for a in articles if a.get("trend_score", 0) >= 60 and a.get("risk_score", 0) < 70]),
            "positiveCount": sent_counts.get("positive", 0),
            "negativeCount": sent_counts.get("negative", 0),
            "neutralCount": sent_counts.get("neutral", 0),
            "sourcesCount": source_count
        },
        "errors": []
    }


# ── Report Download Endpoints ─────────────────────────────────────


@router.get("/api/report/download/{client_id}")
async def download_report(client_id: str, date: str = None):
    """Download the latest PDF report for a client from Redis cache."""
    from core.cache_client import get_cache
    r = await get_cache()
    if not r:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")
    pdf_bytes = await r.get(f"report:{client_id}:{date}")
    if not pdf_bytes:
        raise HTTPException(status_code=404, detail="Report not generated yet for this date. POST /api/report/generate/{client_id} first.")
    raw = pdf_bytes if isinstance(pdf_bytes, bytes) else pdf_bytes.encode("latin-1")
    return Response(
        content=raw,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=VeeTrack_{client_id}_{date}.pdf"},
    )


@router.post("/api/report/generate/{client_id}")
async def trigger_report_now(client_id: str):
    """Manually trigger report generation for a client (requires Celery)."""
    try:
        from tasks.report_tasks import generate_and_send_report
        task = generate_and_send_report.delay(client_id)
        return {"status": "queued", "task_id": task.id, "client_id": client_id}
    except Exception as e:
        # If Celery not running, generate synchronously
        from services.report_generator import generate_daily_report_pdf
        from core.cache_client import get_cache
        from datetime import datetime

        today = datetime.utcnow().strftime("%Y-%m-%d")
        r = await get_cache()
        pdf_bytes = generate_daily_report_pdf(
            client_name=client_id.upper(),
            date=today,
            company_articles=[],
            competition_articles=[],
            industry_articles=[],
        )
        if r:
            await r.setex(f"report:{client_id}:{today}", 172800, pdf_bytes)
        return {"status": "generated_sync", "client_id": client_id, "note": str(e)}
