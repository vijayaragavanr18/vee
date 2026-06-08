import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from services.faiss_service import faiss_service
# Other imports to be added later as needed

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    logger.info("Initializing VeeTrack Backend...")
    
    # 1. Load FAISS from latest checkpoint
    logger.info("Loading FAISS checkpoint...")
    success = faiss_service.load_from_checkpoint()
    if success:
        # In a real scenario, we'd trigger rebuild_since() here
        pass
    else:
        logger.info("Starting with empty FAISS index.")
        
    yield
    
    # Shutdown actions
    logger.info("Shutting down VeeTrack Backend...")
    
    # Checkpoint FAISS gracefully before shutdown
    try:
        faiss_service.checkpoint()
    except Exception as e:
        logger.error(f"Failed to checkpoint FAISS on shutdown: {e}")
