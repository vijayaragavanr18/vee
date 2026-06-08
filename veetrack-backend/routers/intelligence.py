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

class ArticleStreamRequest(BaseModel):
    title: str
    content: str
    url: str = None

class ScrapeRequest(BaseModel):
    url: str


def _determine_risk_level(avg_risk: float) -> str:
    if avg_risk >= 70:
        return "critical"
    elif avg_risk >= 50:
        return "high"
    elif avg_risk >= 30:
        return "medium"
    return "low"


def _generate_executive_brief_algorithmic(client_name: str, keyword: str, articles: list) -> dict:
    if not articles:
        return {
            "happened": f'No significant coverage found for "{keyword}".',
            "whyItMatters": "Low media presence.",
            "recommendedAction": "Consider proactive content seeding.",
            "riskLevel": "LOW",
        }

    # Find the article with the highest risk score or trend score
    top_article = sorted(articles, key=lambda a: a.get("risk_score", 0) + a.get("trend_score", 0), reverse=True)[0]
    avg_risk = sum(a.get("risk_score", 0) for a in articles) / len(articles)
    
    happened = top_article.get("summary", "")
    if not happened or len(happened) < 20:
        happened = top_article.get("title", f"Multiple reports concerning {keyword} have emerged.")

    if avg_risk >= 70:
        why = f"High volume of critical coverage threatens {keyword}'s public perception."
        action = "URGENT: Monitor for crisis escalation and alert leadership."
        risk = "CRITICAL"
    elif avg_risk >= 50:
        why = f"Elevated negative sentiment forming around {keyword}."
        action = "FLAG: Prepare holding statements in case volume increases."
        risk = "HIGH"
    elif avg_risk >= 30:
        why = f"Moderate mixed coverage regarding {keyword}."
        action = "Routine monitoring."
        risk = "MEDIUM"
    else:
        why = f"Coverage surrounding {keyword} remains stable and neutral-to-positive."
        action = "Archive for weekly intelligence reporting."
        risk = "LOW"

    return {
        "happened": happened[:200] + "..." if len(happened) > 200 else happened,
        "whyItMatters": why,
        "recommendedAction": action,
        "riskLevel": risk,
    }


def generate_instant_summary(text: str, sentences_count: int = 3) -> str:
    if not text or len(text.strip()) < 50:
        return text
    try:
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.summarizers.lsa import LsaSummarizer
        
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LsaSummarizer()
        summary = summarizer(parser.document, sentences_count)
        return " ".join([str(sentence) for sentence in summary])
    except Exception as e:
        logger.error(f"Sumy failed: {e}")
        return text[:500] + "..."

@router.post("/api/intelligence")
async def get_intelligence(req: IntelligenceRequest):
    """
    Generate a full intelligence report.
    Uses Sumy to instantly summarize ALL articles.
    """
    raw = await fetch_all_sources(req.keywords, days=req.days)
    articles = await process_articles(raw)
    keyword = req.keywords[0] if req.keywords else ""

    # ── Statistics ──
    by_source: dict[str, int] = {}
    for a in articles:
        src = a.get("source", a.get("origin", "unknown"))
        by_source[src] = by_source.get(src, 0) + 1

    def _get_sentiment(a):
        s = a.get("sentiment", "neutral")
        return s.get("label", "neutral") if isinstance(s, dict) else s

    sent_counts = Counter(_get_sentiment(a) for a in articles)
    
    entity_counter: Counter = Counter()
    entity_type_map: dict[str, str] = {}
    for a in articles:
        for e in a.get("entities", []):
            text = e.get("text", "")
            label = e.get("label", "Topic")
            type_map = {"ORG": "Organization", "PERSON": "Person", "GPE": "Location"}
            entity_counter[text] += 1
            entity_type_map[text] = type_map.get(label, "Topic")

    avg_risk = sum(a.get("risk_score", 0) for a in articles) / len(articles) if articles else 0
    risk_level = _determine_risk_level(avg_risk)
    source_count = len(by_source)

    llm_brief = _generate_executive_brief_algorithmic(keyword, keyword, articles)

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
        
        content = a.get("body_text", "")
        if not content or len(content) < 50:
            content = a.get("summary", a.get("title", ""))
            
        # INSTANT SUMMARY FOR EVERY ARTICLE
        what_happened_text = generate_instant_summary(content, 3)
        why_it_matters_text = a.get("why_it_matters", generate_instant_summary(content, 2))

        return {
            "id": a.get("id", f"art-{datetime.now().timestamp()}"),
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
            "entities": {"people": people, "organizations": orgs, "locations": locs},
            "sarcasmFlag": False,
            "sarcasmReason": "",
            "businessImpact": a.get("why_it_matters", a.get("whyItMatters", "")),
            "llm_what_happened": what_happened_text,
            "llm_why_it_matters": why_it_matters_text,
            "llm_ai_narrative": f"Executive Overview: {what_happened_text}",
            "tone": "Informative",
            "keyQuote": "",
            "relevanceScore": a.get("risk_score", a.get("riskScore", 0)),
            "relevanceExplanation": a.get("suggested_action", a.get("suggestedAction", "")),
            "isPriority": a.get("trend_score", a.get("trendScore", 0)) >= 60
        }

    scored_articles = [map_to_scored_article(a) for a in articles]

    base_report = {
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
            "totalFound": len(raw),
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
    
    return base_report

@router.post("/api/intelligence/stream-article")
async def stream_article_analysis(req: ArticleStreamRequest):
    import os, json, httpx
    from fastapi.responses import StreamingResponse
    
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
    
    prompt = f"""You are a Senior Corporate Intelligence Analyst at an elite PR tracking firm. 
Provide a master-level, highly elaborate analysis of the following article. Your analysis must be massively comprehensive, literally filling a full-page executive report.

ARTICLE: {req.title}
CONTENT TO ANALYZE:
{{ARTICLE_TEXT}}

Write exactly four detailed sections. You MUST write a MINIMUM of 150 words for EACH section. Do not summarize briefly. Expand aggressively on the strategic insights, market context, and corporate intelligence. Use a highly professional, authoritative tone.

Format your response exactly like this:

WHAT HAPPENED:
[Write at least 150 words here. Massive, extremely elaborate multi-sentence analysis detailing the core events, background context, key players, and specific facts mentioned in the article. Expand aggressively.]

WHY IT MATTERS:
[Write at least 150 words here. Massive, extremely elaborate multi-sentence analysis explaining the strategic business impact, market consequences, brand reputation implications, and deep industry consequences. Expand aggressively.]

AI NARRATIVE:
[Write at least 150 words here. A massive, storytelling-style cognitive POV narrative that connects this event to broader industry trends, historical context, and gives a comprehensive, immersive summary of the strategic landscape. Expand aggressively.]

SUGGESTED ACTIONS & IMPACT:
[Write at least 150 words here. Massive, highly interactive and strategic playbook detailing exactly what PR and leadership should do, the potential risks if ignored, and the projected impact of these actions. Expand aggressively.]
"""

    async def generate_response():
        article_text = req.content[:15000]
        
        cached_text = None
        if req.url:
            from core.cache_client import get_cache
            cache = await get_cache()
            cached_text = await cache.get(f"scrape:{req.url}")
            if cached_text:
                article_text = cached_text
                logger.info(f"[Cache Hit] Instant load for streaming: {req.url}")

        # Only scrape if we don't already have the full content from Cache/Ingestion
        if not cached_text and len(req.content) < 1000 and req.url and req.url.startswith("http"):
            try:
                # Try Jina Reader first (Instant, API-based)
                async with httpx.AsyncClient(timeout=10.0) as fetch_client:
                    jina_res = await fetch_client.get(f"https://r.jina.ai/{req.url}")
                    if jina_res.status_code == 200 and len(jina_res.text) > 500:
                        article_text = jina_res.text[:8000]
                        logger.info(f"Jina API instantly extracted {len(article_text)} chars from {req.url}")
                    else:
                        raise Exception("Jina failed or returned too little data")
            except Exception as e:
                logger.warning(f"Jina API failed ({e}), falling back to local Crawl4AI...")
                try:
                    from crawl4ai import AsyncWebCrawler
                    async with AsyncWebCrawler(verbose=False) as crawler:
                        result = await crawler.arun(url=req.url, bypass_cache=True)
                        if result and result.markdown:
                            article_text = result.markdown[:8000]
                            logger.info(f"Crawl4AI successfully extracted {len(article_text)} chars from {req.url}")
                except Exception as crawl_e:
                    logger.error(f"Crawl4AI fallback failed for {req.url}: {crawl_e}")
        
        final_prompt = prompt.replace("{ARTICLE_TEXT}", article_text)

        openrouter_key = os.getenv("OPENROUTER_API_KEY")

        try:
            async with httpx.AsyncClient(timeout=900.0) as client:
                if openrouter_key:
                    # Use OpenRouter
                    headers = {
                        "Authorization": f"Bearer {openrouter_key}",
                        "HTTP-Referer": "http://localhost:3000",
                        "X-Title": "VeeTrack"
                    }
                    payload = {
                        "model": os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"),
                        "messages": [{"role": "user", "content": final_prompt}],
                        "stream": True,
                        "temperature": 0.5
                    }
                    async with client.stream("POST", "https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload) as response:
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                data_str = line[6:]
                                if data_str.strip() == "[DONE]":
                                    continue
                                try:
                                    data = json.loads(data_str)
                                    if "choices" in data and len(data["choices"]) > 0:
                                        chunk = data["choices"][0].get("delta", {}).get("content", "")
                                        if chunk:
                                            yield json.dumps({"type": "chunk", "chunk": chunk}) + "\n"
                                except Exception as parse_e:
                                    continue
                else:
                    # Use Local Ollama
                    async with client.stream("POST", ollama_url, json={
                        "model": ollama_model,
                        "prompt": final_prompt,
                        "stream": True,
                        "options": {"temperature": 0.5, "num_predict": 4096, "num_ctx": 8192},
                    }) as response:
                        async for line in response.aiter_lines():
                            if line:
                                data = json.loads(line)
                                chunk = data.get("response", "")
                                if chunk:
                                    yield json.dumps({"type": "chunk", "chunk": chunk}) + "\n"
        except Exception as e:
            logger.error(f"On-demand streaming failed: {e}")
            yield json.dumps({"type": "chunk", "chunk": "Error generating analysis."}) + "\n"
            
        yield json.dumps({"type": "done"}) + "\n"

    return StreamingResponse(generate_response(), media_type="application/x-ndjson")

@router.post("/api/scrape-article")
async def scrape_article(req: ScrapeRequest):
    if not req.url or not req.url.startswith("http"):
        return {"content": "<p>Invalid or missing URL.</p>"}
        
    from core.cache_client import get_cache
    cache = await get_cache()
    cached_text = await cache.get(f"scrape:{req.url}")
    if cached_text:
        html_content = cached_text.replace("\n\n", "</p><p>").replace("\n", "<br/>")
        logger.info(f"[Cache Hit] Instant load for modal reader: {req.url}")
        return {"content": f"<p>{html_content}</p>"}

    try:
        # Fast API Scraping Integration (Jina Reader)
        async with httpx.AsyncClient(timeout=10.0) as fetch_client:
            jina_res = await fetch_client.get(f"https://r.jina.ai/{req.url}")
            if jina_res.status_code == 200 and len(jina_res.text) > 500:
                # Convert markdown to basic HTML for the frontend reader
                html_content = jina_res.text.replace("\n\n", "</p><p>").replace("\n", "<br/>")
                return {"content": f"<p>{html_content}</p>"}
    except Exception as e:
        logger.warning(f"Jina API failed for reading ({e}), falling back to Crawl4AI...")

    try:
        from crawl4ai import AsyncWebCrawler
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=req.url, bypass_cache=True)
            
            # Use markdown or cleaned HTML if available
            html_content = result.html
            if not html_content and result.markdown:
                # Basic markdown to HTML fallback
                html_content = result.markdown.replace("\n\n", "</p><p>").replace("\n", "<br/>")
                html_content = f"<p>{html_content}</p>"
                
            if html_content:
                return {"content": html_content}
    except Exception as e:
        logger.error(f"Crawl4AI scrape failed for {req.url}: {e}")
        
    return {"content": "<p>Failed to retrieve the full article from the original source. The site may have blocking protections.</p>"}


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
            await r.set(f"report:{client_id}:{today}", pdf_bytes, ex=172800)
        return {"status": "generated_sync", "client_id": client_id, "note": str(e)}
