import os
from fastapi import FastAPI
from prometheus_client import make_asgi_app
import structlog
from fastapi.middleware.cors import CORSMiddleware

from startup import lifespan
from observability.logging import setup_logging
from observability.metrics import MetricsMiddleware
from middleware.rate_limit import RateLimitMiddleware

# Routers
from routers import auth, health, stats, graph, reports, intelligence
from routers.admin import sources as admin_sources

# Initialize structured logging
setup_logging()
logger = structlog.get_logger()

# Create FastAPI app with Lifespan
app = FastAPI(
    title="VeeTrack Enterprise API",
    version="2.0.0",
    lifespan=lifespan
)

# CORS Middleware
FRONTEND_DOMAIN = os.getenv("FRONTEND_DOMAIN", "https://app.veetrack.com")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_DOMAIN, "http://localhost:5173"], # Restricted CORS policy
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Rate Limiting & Metrics Middleware
# Order matters: Rate limits happen before metrics to drop spam early
app.add_middleware(MetricsMiddleware)
app.add_middleware(RateLimitMiddleware)

# Expose Prometheus Metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Include API Routers
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(stats.router)
app.include_router(graph.router)
app.include_router(reports.router)
app.include_router(admin_sources.router)
app.include_router(intelligence.router)

@app.get("/")
async def root():
    logger.info("Root endpoint accessed.")
    return {"message": "Welcome to VeeTrack API v2.0 Enterprise Mode."}
