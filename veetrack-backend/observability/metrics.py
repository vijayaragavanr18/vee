import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "http_requests_total", 
    "Total HTTP Requests", 
    ["method", "endpoint", "http_status"]
)

REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP Request Latency",
    ["method", "endpoint"]
)

class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # We don't want to metric the /metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)
            
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Basic path matching to avoid cardinality explosion on dynamic IDs
        path = request.url.path
        if "/entity/" in path:
            path = "/graph/entity/{name}"
            
        REQUEST_COUNT.labels(
            method=request.method, 
            endpoint=path, 
            http_status=response.status_code
        ).inc()
        
        REQUEST_LATENCY.labels(
            method=request.method, 
            endpoint=path
        ).observe(process_time)
        
        return response
