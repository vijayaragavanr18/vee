"""
VeeTrack — FastAPI application entry point.

Primary backend for the VeeTrack media intelligence platform.
Next.js is a thin proxy — all business logic lives here.

Routers:
  - feed            (POST /api/feed)
  - intelligence    (POST /api/intelligence)
  - chat            (POST/DELETE /api/chat, POST /api/chat/ask)
  - reactions       (POST /api/reactions)
  - alerts          (GET /api/alerts — SSE)
  - tracking_brief  (GET/POST /api/tracking-brief)
"""

# ── Load root .env (single source of truth) ──────────────────────
from __future__ import annotations
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager

_backend_dir = Path(__file__).parent
_root_env = _backend_dir.parent / ".env"    # monorepo root
_local_env = _backend_dir / ".env"          # legacy fallback

_env_file = _root_env if _root_env.exists() else _local_env
if _env_file.exists():
    from dotenv import load_dotenv
    load_dotenv(_env_file, override=False)


import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import alerts, chat, feed, intelligence, reactions
from routers.tracking_brief import router as tracking_brief_router

# ── Logging ──────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("veetrack")

# ── Lifespan (startup / shutdown) ────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from core.cache_client import get_cache, cache_available
    try:
        r = await get_cache()
        app.state.cache = r
        is_up = await cache_available()
        if is_up:
            logger.info("DiskCache (Local DB) connected ✓")
        else:
            logger.warning("Local Cache unavailable — trend history will be in-memory only")
    except Exception as e:
        logger.warning(f"Cache startup error: {e}")
        app.state.cache = None
    yield
    # Shutdown
    try:
        if hasattr(app.state, "redis") and app.state.cache:
            await app.state.cache.aclose()
    except Exception:
        pass


# ── App Factory ──────────────────────────────────────────────────

app = FastAPI(
    title="VeeTrack API",
    description="Media Intelligence Platform — real-time news & social intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        'ALLOWED_ORIGINS',
        'http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173,http://localhost'
    ).split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────

app.include_router(feed.router)
app.include_router(intelligence.router)
app.include_router(chat.router)
app.include_router(reactions.router)
app.include_router(alerts.router)
app.include_router(tracking_brief_router)


# ── Health Check ─────────────────────────────────────────────────


@app.get("/health")
async def health():
    """Basic health check endpoint."""
    from core.cache_client import cache_available
    redis_up = await cache_available()
    return {
        "status": "ok",
        "service": "veetrack-backend",
        "version": "1.0.0",
        "redis": "connected" if redis_up else "unavailable",
    }


@app.get("/")
async def root():
    """Root endpoint with basic info."""
    return {
        "name": "VeeTrack",
        "version": "1.0.0",
        "description": "Media Intelligence Platform",
        "docs": "/docs",
        "health": "/health",
    }


# ── Entry Point ──────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
