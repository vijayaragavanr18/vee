import logging
from celery_app import app

logger = logging.getLogger(__name__)

@app.task(queue='dead_letters')
def dlq_handler(failed_task_name: str, args: list, kwargs: dict, error_msg: str):
    """
    Dead Letter Queue Handler.
    Called manually when a task exhausts all its retries.
    """
    logger.error(
        f"DLQ TRIGGERED: Task {failed_task_name} failed permanently. "
        f"Args: {args}, Kwargs: {kwargs}. Error: {error_msg}"
    )
    # In a real system, you might save this to a DLQ table in Postgres here.
    return {"status": "moved_to_dlq"}

def exponential_backoff(retries: int) -> int:
    """Returns 2^n seconds for backoff"""
    return 2 ** retries

# Base task that implements auto-DLQ on failure
class DLQTask(app.Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        if self.request.retries >= self.max_retries:
            dlq_handler.apply_async(
                args=[self.name, args, kwargs, str(exc)],
                queue='dead_letters'
            )
        super().on_failure(exc, task_id, args, kwargs, einfo)

@app.task(bind=True, base=DLQTask, max_retries=3)
def process_article(self, article_data: dict):
    """
    The main pipeline for a single article.
    We will implement asyncio.gather for CPU models and call vLLM.
    """
    try:
        import asyncio
        from services.model_manager import ModelManager
        # Placeholder for full pipeline implementation in later steps
        logger.info(f"Processing article: {article_data.get('url')}")
        # To be implemented in Step 4/5
        return {"status": "success", "url": article_data.get('url')}
    except Exception as exc:
        delay = exponential_backoff(self.request.retries)
        logger.warning(f"Task failed, retrying in {delay}s. Error: {exc}")
        raise self.retry(exc=exc, countdown=delay)
