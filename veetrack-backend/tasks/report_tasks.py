"""Report generation Celery tasks — daily PDF generation and email delivery."""
from __future__ import annotations
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from celery_app import app
    from services.report_generator import generate_daily_report_pdf, send_report_email
    from core.cache_client import get_sync_cache

    redis_sync = get_sync_cache()

    @app.task
    def generate_and_send_report(client_id: str):
        """Generate PDF report for one client and email it."""
        try:
            if not redis_sync:
                return {"error": "Redis unavailable"}
            brief_raw = redis_sync.get(f"brief:{client_id}")
            if not brief_raw:
                logger.warning(f"No brief for {client_id}")
                return {"error": f"No brief for {client_id}"}

            brief = json.loads(brief_raw)
            today = datetime.utcnow().strftime("%Y-%m-%d")

            def get_articles(keyword_configs):
                articles = []
                for kc in keyword_configs:
                    kw = kc["keyword"] if isinstance(kc, dict) else kc.keyword
                    cached = redis_sync.get(f"feed:{kw.lower().replace(' ', '_')}")
                    if cached:
                        articles.extend(json.loads(cached))
                seen, unique = set(), []
                for a in articles:
                    url = a.get("url", "")
                    if url and url not in seen:
                        seen.add(url)
                        unique.append(a)
                return unique

            company = get_articles(brief.get("company_keywords", []))
            competition = get_articles(brief.get("competition_keywords", []))
            industry = get_articles(brief.get("industry_keywords", []))

            pdf_bytes = generate_daily_report_pdf(
                client_name=brief.get("client_name", client_id),
                date=today,
                company_articles=company,
                competition_articles=competition,
                industry_articles=industry,
            )

            # Save to Redis for download
            if pdf_bytes:
                redis_sync.set(f"report:{client_id}:{today}", pdf_bytes, ex=172800)

            # Email the report
            send_report_email(
                to_email=brief.get("report_email", ""),
                client_name=brief.get("client_name", client_id),
                date=today,
                pdf_bytes=pdf_bytes,
            )

            return {
                "client_id": client_id,
                "date": today,
                "articles": len(company) + len(competition) + len(industry),
            }
        except Exception as e:
            logger.error(f"Report generation failed for {client_id}: {e}")
            return {"error": str(e)}

    @app.task
    def send_all_daily_reports():
        """Send reports for ALL configured clients. Runs at 8AM IST via Celery beat."""
        if not redis_sync:
            return {"triggered": 0}
        client_ids = redis_sync.smembers("all_clients") or set()
        triggered = 0
        for cid in client_ids:
            cid = cid if isinstance(cid, str) else cid.decode()
            generate_and_send_report.delay(cid)
            triggered += 1
        return {"triggered": triggered}

except ImportError as e:
    logger.warning(f"Celery not available: {e}. Report tasks disabled.")
