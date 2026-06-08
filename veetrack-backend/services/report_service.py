import os
import logging
from datetime import datetime, timedelta
from jinja2 import Environment, FileSystemLoader
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except OSError as e:
    import logging
    logger = logging.getLogger(__name__)
    logger.warning("WeasyPrint GTK dependencies not found. PDF generation will be disabled.")
    WEASYPRINT_AVAILABLE = False
from sqlalchemy.future import select

from database import async_session_factory
from models import Article, IntelligenceCard, ClusterAssignment, ClusterVersion
from services.llm_service import analyze_article # Reusing for generic generation if needed

logger = logging.getLogger(__name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")
REPORTS_DIR = os.getenv("REPORTS_DIR", "/tmp/veetrack_reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

class ReportService:
    def __init__(self):
        self.jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

    async def _generate_cluster_summary(self, articles_text: str) -> str:
        """Uses vLLM to summarize a cluster of articles."""
        # For simplicity, bypassing guided decoding for generic text summary
        import httpx
        from services.llm_service import VLLM_URL, MODEL
        prompt = "Summarize the following group of related news articles into one concise executive paragraph.\n\n" + articles_text
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                res = await client.post(VLLM_URL, json={
                    "model": MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                })
                return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Failed to generate cluster summary: {e}")
            return "Summary unavailable."

    async def generate_daily_pdf(self) -> str:
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        
        async with async_session_factory() as session:
            # 1. Get latest cluster version
            result = await session.execute(select(ClusterVersion).order_by(ClusterVersion.created_at.desc()).limit(1))
            latest_version = result.scalar_one_or_none()
            
            if not latest_version:
                logger.warning("No clusters available for report.")
                return ""
                
            # 2. Fetch assignments + articles + cards
            result = await session.execute(
                select(ClusterAssignment.cluster_id, Article, IntelligenceCard)
                .join(Article, Article.id == ClusterAssignment.article_id)
                .join(IntelligenceCard, IntelligenceCard.article_id == Article.id)
                .where(ClusterAssignment.version_id == latest_version.id)
            )
            data = result.all()
            
        # Group by cluster
        clusters = {}
        for c_id, article, card in data:
            if c_id not in clusters:
                clusters[c_id] = {"id": c_id, "articles": [], "text_blob": ""}
            
            clusters[c_id]["articles"].append({
                "title": article.title,
                "sentiment": card.sentiment,
                "risk_level": card.risk_level,
                "executive_summary": card.executive_summary
            })
            clusters[c_id]["text_blob"] += f"Title: {article.title}\n{card.executive_summary}\n\n"

        # Generate AI summary for each cluster
        cluster_list = []
        for c_id, c_data in clusters.items():
            ai_summary = await self._generate_cluster_summary(c_data["text_blob"][:4000]) # cap length
            c_data["ai_summary"] = ai_summary
            cluster_list.append(c_data)
            
        # Render HTML
        template = self.jinja_env.get_template("daily_report.html")
        html_out = template.render(
            date=now.strftime("%Y-%m-%d"),
            clusters=cluster_list
        )
        
        # Generate PDF
        pdf_filename = f"daily_brief_{now.strftime('%Y%m%d')}.pdf"
        pdf_path = os.path.join(REPORTS_DIR, pdf_filename)
        
        if not WEASYPRINT_AVAILABLE:
            raise Exception("PDF export is unavailable because WeasyPrint dependencies (GTK3) are not installed on this system.")
        
        HTML(string=html_out).write_pdf(pdf_path)
        logger.info(f"Generated daily PDF report: {pdf_path}")
        return pdf_path

    async def export_pdf_report(self, keyword: str, articles: list[dict]) -> str:
        if not WEASYPRINT_AVAILABLE:
            raise Exception("PDF export is unavailable because WeasyPrint dependencies (GTK3) are not installed on this system.")
            
        html_content = self.jinja_env.get_template("daily_report.html").render(keyword=keyword, articles=articles)
        pdf_path = os.path.join(REPORTS_DIR, f"VeeTrack_Report_{keyword.replace(' ', '_')}.pdf")
        HTML(string=html_content).write_pdf(pdf_path)
        return pdf_path

report_service = ReportService()
