import logging
import asyncio
from datetime import datetime
from sqlalchemy.future import select

from celery_app import app
from database import async_session_factory
from models import NewsSource, FetchLog
from services.ingestion_service import ingestion_service

logger = logging.getLogger(__name__)

async def _process_source(source_id: str):
    async with async_session_factory() as session:
        result = await session.execute(select(NewsSource).where(NewsSource.id == source_id))
        source = result.scalar_one_or_none()
        
        if not source or not source.is_active:
            return
            
        articles = []
        error_msg = None
        status = "success"
        
        try:
            if source.source_type == "rss":
                articles = await ingestion_service.fetch_rss(source.url)
            elif source.source_type == "url":
                articles = await ingestion_service.fetch_url(source.url)
            elif source.source_type == "newsdata":
                articles = await ingestion_service.fetch_newsdata(source.url)
            elif source.source_type == "freenews":
                articles = await ingestion_service.fetch_freenews(source.url)
            elif source.source_type == "currents":
                articles = await ingestion_service.fetch_currents(source.url)
            elif source.source_type == "gdelt":
                articles = await ingestion_service.fetch_gdelt(source.url)
            elif source.source_type == "youtube":
                articles = await ingestion_service.fetch_youtube(source.url)
            elif source.source_type == "reddit":
                articles = await ingestion_service.fetch_reddit(source.url)
                
            source.consecutive_failures = 0
            
        except Exception as e:
            status = "error"
            error_msg = str(e)
            source.consecutive_failures += 1
            if source.consecutive_failures >= 5:
                source.is_active = False
                logger.warning(f"Source {source.name} disabled after 5 failures.")
                
        # Create fetch log
        log = FetchLog(
            source_id=source.id,
            status=status,
            error_message=error_msg,
            articles_found=len(articles)
        )
        source.last_fetched = datetime.utcnow()
        session.add(log)
        await session.commit()
        
        # If success, trigger pipeline for articles
        if status == "success" and articles:
            # Here we would send them to the article_pipeline Celery task
            # For each article: check deduplication of URL first
            from tasks.article_pipeline import process_article
            for article in articles:
                # Dispatch async Celery task
                process_article.delay(article)

@app.task(queue='cpu')
def fetch_source_task(source_id: str):
    """Celery task to fetch a single source."""
    asyncio.run(_process_source(source_id))

@app.task(queue='scheduled')
def trigger_news_ingestion():
    """Triggered by beat schedule every 15 mins. Finds due sources."""
    async def _trigger():
        async with async_session_factory() as session:
            result = await session.execute(select(NewsSource).where(NewsSource.is_active == True))
            sources = result.scalars().all()
            for source in sources:
                # In a real impl, we check if `last_fetched + interval` is past
                fetch_source_task.delay(source.id)
    asyncio.run(_trigger())
    return "ingestion_triggered"
