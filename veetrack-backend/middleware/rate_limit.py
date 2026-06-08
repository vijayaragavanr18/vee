import time
import os
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis
from jose import jwt, JWTError

from auth.jwt import SECRET_KEY, ALGORITHM

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL)

ROLE_LIMITS = {
    "admin": 1000,
    "analyst": 200,
    "viewer": 60,
    "anonymous": 10
}

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path.startswith("/health"):
            return await call_next(request)
            
        role = "anonymous"
        identifier = request.client.host if request.client else "unknown_ip"
        
        # Try to extract role from auth header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                if payload.get("type") == "access":
                    role = payload.get("role", "anonymous")
                    identifier = payload.get("sub", identifier)
            except JWTError:
                pass
                
        # API Key fast track
        api_key = request.headers.get("X-API-Key")
        if api_key:
            role = "admin"
            identifier = "api_key_service"
            
        limit = ROLE_LIMITS.get(role, 10)
        
        # Redis rate limit logic (sliding window or simple counter)
        # Using simple minute bucket counter for performance
        current_minute = int(time.time() / 60)
        redis_key = f"rate_limit:{identifier}:{current_minute}"
        
        try:
            # Use pipeline to execute increment and expire atomically
            pipe = redis_client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, 60)
            result = await pipe.execute()
            
            current_count = result[0]
            if current_count > limit:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": f"Rate limit exceeded. Max {limit} requests per minute for role '{role}'."}
                )
        except redis.RedisError:
            # Fail open if Redis is down
            pass

        response = await call_next(request)
        return response
