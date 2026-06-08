import os
import logging
from typing import Optional, Any
from diskcache import Cache

logger = logging.getLogger(__name__)

# 10 GB limit
MAX_CACHE_SIZE_BYTES = 10 * 1024 * 1024 * 1024
EVICTION_THRESHOLD = 0.90 # 90%
TTL_SECONDS = 6 * 3600 # 6 hours

CACHE_DIR = os.getenv("CACHE_DIR", ".veetrack_cache")

class CacheService:
    def __init__(self):
        # We configure size_limit to let diskcache handle some native eviction,
        # but we also wrap it to manually track stats and force LRU.
        self.cache = Cache(CACHE_DIR, size_limit=MAX_CACHE_SIZE_BYTES)
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        value = self.cache.get(key)
        if value is not None:
            self.hits += 1
            return value
        self.misses += 1
        return None

    def set(self, key: str, value: Any):
        self._check_eviction()
        self.cache.set(key, value, expire=TTL_SECONDS)

    def _check_eviction(self):
        """Manually trigger LRU eviction if cache is too large."""
        try:
            # size is approximate
            size = self.cache.volume()
            if size > (MAX_CACHE_SIZE_BYTES * EVICTION_THRESHOLD):
                logger.warning(f"Cache >90% full ({size/(1024**3):.2f}GB). Evicting old entries.")
                # diskcache `cull` removes expired and old items
                self.cache.cull()
        except Exception as e:
            logger.error(f"Failed cache eviction check: {e}")

    def get_stats(self) -> dict:
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        size_bytes = self.cache.volume()
        
        return {
            "size_gb": round(size_bytes / (1024**3), 3),
            "utilization_pct": round((size_bytes / MAX_CACHE_SIZE_BYTES) * 100, 2),
            "hit_rate_24h": round(hit_rate, 1),
            "hits": self.hits,
            "misses": self.misses,
            "ttl_seconds": TTL_SECONDS
        }

cache_service = CacheService()
