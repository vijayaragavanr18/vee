from fastapi import APIRouter
import torch

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/vram")
async def get_vram_health():
    """Returns exact GPU memory utilization."""
    if not torch.cuda.is_available():
        return {"status": "cpu_only", "gpu_count": 0}
        
    devices = []
    for i in range(torch.cuda.device_count()):
        # torch returns bytes, convert to GB
        allocated = torch.cuda.memory_allocated(i) / (1024**3)
        reserved = torch.cuda.memory_reserved(i) / (1024**3)
        max_mem = torch.cuda.get_device_properties(i).total_memory / (1024**3)
        
        devices.append({
            "device_id": i,
            "name": torch.cuda.get_device_name(i),
            "allocated_gb": round(allocated, 2),
            "reserved_gb": round(reserved, 2),
            "total_capacity_gb": round(max_mem, 2),
            "utilization_pct": round((reserved / max_mem) * 100, 1) if max_mem > 0 else 0
        })
        
    return {"status": "ok", "gpu_count": len(devices), "devices": devices}

@router.get("/models")
async def get_models_health():
    """Returns status of the CPU-pinned models in ModelManager."""
    from services.model_manager import model_manager
    
    return {
        "gliner_loaded": model_manager._gliner_model is not None,
        "fastembed_loaded": model_manager._embed_model is not None,
        "sentiment_loaded": model_manager._sentiment_model is not None,
        "faiss_gpu_resource_configured": model_manager._faiss_resource is not None
    }

@router.get("/faiss")
async def get_faiss_health():
    """Returns FAISS index stats and checkpoint data."""
    from services.faiss_service import faiss_service
    return {
        "index_size": faiss_service.index.ntotal,
        "articles_indexed": len(faiss_service.article_ids),
        "last_checkpoint_time": faiss_service.last_checkpoint_time
    }

@router.get("/cache")
async def get_cache_health():
    """Returns DiskCache statistics and health."""
    from services.cache_service import cache_service
    stats = cache_service.get_stats()
    
    # Return 429 or warning if >80%
    if stats["utilization_pct"] > 80.0:
        stats["warning"] = "Cache is nearing capacity limit."
        
    return stats
