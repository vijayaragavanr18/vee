import os
from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "veetrack",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.article_pipeline", "tasks.ingestion", "tasks.scheduled"]
)

# Configuration for reliability and retries
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600, # 1 hour hard kill
    task_soft_time_limit=3300,
    broker_connection_retry_on_startup=True,
    task_always_eager=os.getenv("CELERY_ALWAYS_EAGER", "False").lower() == "true",
    
    # Task routing - separate CPU and GPU queues
    task_routes={
        'tasks.article_pipeline.process_article': {'queue': 'gpu'},
        'tasks.scheduled.checkpoint_faiss': {'queue': 'gpu'},
        'tasks.scheduled.log_vram_health': {'queue': 'gpu'},
        'tasks.article_pipeline.dlq_handler': {'queue': 'cpu'},
        'tasks.ingestion.*': {'queue': 'cpu'},
        'tasks.scheduled.*': {'queue': 'cpu'}
    },
    
    # Dead letter routing (if a task fails completely after retries, we manually route it to DLQ in the task logic)
    task_reject_on_worker_lost=True,
    task_acks_late=True,
)

# Celery Beat Schedule
app.conf.beat_schedule = {
    'ingest-news-every-15-min': {
        'task': 'tasks.scheduled.trigger_news_ingestion',
        'schedule': crontab(minute='*/15'),
    },
    'generate-daily-pdf-report': {
        'task': 'tasks.scheduled.generate_daily_pdf',
        'schedule': crontab(hour=6, minute=0),
    },
    'checkpoint-faiss-every-hour': {
        'task': 'tasks.scheduled.checkpoint_faiss',
        'schedule': crontab(minute=0), # Top of every hour
    },
    'log-vram-health-every-5-min': {
        'task': 'tasks.scheduled.log_vram_health',
        'schedule': crontab(minute='*/5'),
    },
    'recompute-hdbscan-clusters-daily': {
        'task': 'tasks.scheduled.recompute_clusters',
        'schedule': crontab(hour=2, minute=0),
    }
}
