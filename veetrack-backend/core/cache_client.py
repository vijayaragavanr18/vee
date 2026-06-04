"""
DiskCache client singleton for VeeTrack backend.
Replaces Redis to provide a 100% portable, self-contained architecture.
"""
from __future__ import annotations
import os
import fnmatch
from diskcache import Cache

CACHE_DIR = os.getenv("CACHE_DIR", ".veetrack_cache")
# Thread-safe, process-safe cache
_cache = Cache(CACHE_DIR)

class AsyncCache:
    async def get(self, key: str) -> str | None:
        return _cache.get(key)
        
    async def set(self, key: str, value: str, ex: int | None = None):
        _cache.set(key, value, expire=ex)
        
    async def keys(self, pattern: str) -> list[str]:
        return [k for k in _cache.iterkeys() if fnmatch.fnmatch(k, pattern)]
        
    async def delete(self, *keys):
        for k in keys:
            _cache.delete(k)
            
    async def ping(self):
        return True
        
    async def aclose(self):
        # We don't close the global cache per request
        pass
        
    async def publish(self, channel: str, message: str):
        # Cross-process pub/sub not supported without Redis.
        # Fallback polling mechanisms will take over.
        pass
        
    def pubsub(self):
        raise RuntimeError("Pub/Sub not supported by DiskCache fallback")

    async def sadd(self, key: str, *values: str):
        import json
        existing = _cache.get(key)
        s = set(json.loads(existing)) if existing else set()
        for v in values:
            s.add(v)
        _cache.set(key, json.dumps(list(s)))

    async def smembers(self, key: str) -> set:
        import json
        existing = _cache.get(key)
        return set(json.loads(existing)) if existing else set()

    async def srem(self, key: str, *values: str):
        import json
        existing = _cache.get(key)
        if existing:
            s = set(json.loads(existing))
            for v in values:
                s.discard(v)
            _cache.set(key, json.dumps(list(s)))

class SyncCache:
    def get(self, key: str) -> str | None:
        return _cache.get(key)
        
    def set(self, key: str, value: str, ex: int | None = None):
        _cache.set(key, value, expire=ex)
        
    def keys(self, pattern: str) -> list[str]:
        return [k for k in _cache.iterkeys() if fnmatch.fnmatch(k, pattern)]
        
    def delete(self, *keys):
        for k in keys:
            _cache.delete(k)

    def sadd(self, key: str, *values: str):
        import json
        existing = _cache.get(key)
        s = set(json.loads(existing)) if existing else set()
        for v in values:
            s.add(v)
        _cache.set(key, json.dumps(list(s)))

    def smembers(self, key: str) -> set:
        import json
        existing = _cache.get(key)
        return set(json.loads(existing)) if existing else set()

    def srem(self, key: str, *values: str):
        import json
        existing = _cache.get(key)
        if existing:
            s = set(json.loads(existing))
            for v in values:
                s.discard(v)
            _cache.set(key, json.dumps(list(s)))

async def get_cache() -> AsyncCache:
    """Return shared async cache client."""
    return AsyncCache()

def get_sync_cache() -> SyncCache:
    """Return a synchronous cache client (for Celery tasks)."""
    return SyncCache()

async def cache_available() -> bool:
    """Check if cache is reachable."""
    return True
