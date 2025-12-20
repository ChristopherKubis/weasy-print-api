from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZIPMiddleware
from pydantic import BaseModel, Field, field_validator
import psutil
import io
import json
import asyncio
import yaml
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import gc
import os
import hashlib
from collections import OrderedDict
from functools import lru_cache
import time

# Load configuration from config.yml
with open("config.yml", "r") as f:
    config = yaml.safe_load(f)

# Add optimization settings to config if not present
if "optimization" not in config:
    config["optimization"] = {
        "cache_enabled": True,
        "cache_max_size": 100,
        "cache_ttl_seconds": 3600,
        "max_html_size_mb": 10,
        "conversion_timeout_seconds": 30,
        "rate_limit_per_minute": 60,
    }

# Don't import weasyprint at startup - lazy load when needed to save memory

app = FastAPI(
    title="HTML to PDF API",
    description="Optimized API to convert HTML content to PDF using WeasyPrint",
    version="2.0.0",
)

# Add compression middleware
app.add_middleware(GZIPMiddleware, minimum_size=1000)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Statistics
api_stats = {
    "total_requests": 0,
    "successful_conversions": 0,
    "failed_conversions": 0,
    "cache_hits": 0,
    "cache_misses": 0,
    "start_time": datetime.now(),
}

# Request History - use config value
request_history = []
MAX_HISTORY = config["app"]["request_history_max"]

# Container stats tracking
container_stats = {
    "network_io": {"rx_bytes": 0, "tx_bytes": 0},
    "block_io": {"read_bytes": 0, "write_bytes": 0},
}


# PDF Cache using OrderedDict (LRU-like behavior)
class PDFCache:
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self.cache: OrderedDict[str, Dict] = OrderedDict()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def _generate_key(self, html: str) -> str:
        """Generate cache key from HTML content"""
        return hashlib.sha256(html.encode()).hexdigest()

    def get(self, html: str) -> Optional[bytes]:
        """Get cached PDF if exists and not expired"""
        key = self._generate_key(html)
        if key in self.cache:
            entry = self.cache[key]
            if datetime.now() - entry["timestamp"] < timedelta(
                seconds=self.ttl_seconds
            ):
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                return entry["pdf"]
            else:
                # Expired, remove it
                del self.cache[key]
        return None

    def set(self, html: str, pdf: bytes):
        """Cache PDF content"""
        key = self._generate_key(html)

        # Remove oldest if at capacity
        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)

        self.cache[key] = {
            "pdf": pdf,
            "timestamp": datetime.now(),
            "size_kb": len(pdf) / 1024,
        }

    def clear(self):
        """Clear all cache"""
        self.cache.clear()

    def stats(self) -> Dict:
        """Get cache statistics"""
        total_size_kb = sum(entry["size_kb"] for entry in self.cache.values())
        return {
            "entries": len(self.cache),
            "max_size": self.max_size,
            "total_size_kb": round(total_size_kb, 2),
            "ttl_seconds": self.ttl_seconds,
        }


# Initialize cache
pdf_cache = PDFCache(
    max_size=config["optimization"]["cache_max_size"],
    ttl_seconds=config["optimization"]["cache_ttl_seconds"],
)


# Rate limiting
class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = {}

    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed based on rate limit"""
        now = time.time()

        if client_id not in self.requests:
            self.requests[client_id] = []

        # Remove old requests outside the window
        self.requests[client_id] = [
            req_time
            for req_time in self.requests[client_id]
            if now - req_time < self.window_seconds
        ]

        # Check if under limit
        if len(self.requests[client_id]) < self.max_requests:
            self.requests[client_id].append(now)
            return True

        return False

    def cleanup_old_entries(self):
        """Clean up old client entries to prevent memory leak"""
        now = time.time()
        to_remove = []

        for client_id, req_times in self.requests.items():
            # Remove clients with no recent requests
            if not req_times or now - req_times[-1] > self.window_seconds * 2:
                to_remove.append(client_id)

        for client_id in to_remove:
            del self.requests[client_id]


# Initialize rate limiter
rate_limiter = RateLimiter(
    max_requests=config["optimization"]["rate_limit_per_minute"], window_seconds=60
)


@lru_cache(maxsize=1)
def _get_process():
    """Cache process object to avoid recreating it"""
    return psutil.Process()


def get_container_stats():
    """Get Docker container statistics similar to Docker Desktop"""
    process = _get_process()

    # CPU usage (non-blocking, use cached value)
    cpu_percent = process.cpu_percent(interval=0)

    # Memory usage (container-specific)
    memory_info = process.memory_info()
    memory_percent = (memory_info.rss / psutil.virtual_memory().total) * 100

    # Memory limit from config.yml
    memory_limit = (
        config["resources"]["memory"]["limit_gb"] * 1024 * 1024 * 1024
    )  # Convert GB to bytes
    memory_usage_of_limit = (memory_info.rss / memory_limit) * 100

    # Network I/O
    net_io = psutil.net_io_counters()
    net_rx_delta = net_io.bytes_recv - container_stats["network_io"]["rx_bytes"]
    net_tx_delta = net_io.bytes_sent - container_stats["network_io"]["tx_bytes"]
    container_stats["network_io"]["rx_bytes"] = net_io.bytes_recv
    container_stats["network_io"]["tx_bytes"] = net_io.bytes_sent

    # Disk I/O
    disk_io = psutil.disk_io_counters()
    if disk_io:
        disk_read_delta = disk_io.read_bytes - container_stats["block_io"]["read_bytes"]
        disk_write_delta = (
            disk_io.write_bytes - container_stats["block_io"]["write_bytes"]
        )
        container_stats["block_io"]["read_bytes"] = disk_io.read_bytes
        container_stats["block_io"]["write_bytes"] = disk_io.write_bytes
    else:
        disk_read_delta = 0
        disk_write_delta = 0

    # Number of threads (similar to Docker's PIDs)
    num_threads = process.num_threads()

    return {
        "container_name": os.getenv("HOSTNAME", "weasyprint-api"),
        "cpu": {
            "percent": round(cpu_percent, 2),
            "cores": psutil.cpu_count(),
            "limit_cores": config["resources"]["cpu"]["limit_cores"],
        },
        "memory": {
            "used_bytes": memory_info.rss,
            "used_mb": round(memory_info.rss / (1024 * 1024), 2),
            "limit_bytes": memory_limit,
            "limit_gb": config["resources"]["memory"]["limit_gb"],
            "percent_of_limit": round(memory_usage_of_limit, 2),
            "percent_of_system": round(memory_percent, 2),
        },
        "network": {
            "rx_bytes": net_io.bytes_recv,
            "tx_bytes": net_io.bytes_sent,
            "rx_mb": round(net_io.bytes_recv / (1024 * 1024), 2),
            "tx_mb": round(net_io.bytes_sent / (1024 * 1024), 2),
            "rx_delta_per_sec": round(
                net_rx_delta / config["app"]["websocket_update_interval"], 2
            ),  # Per second avg over configured interval
            "tx_delta_per_sec": round(
                net_tx_delta / config["app"]["websocket_update_interval"], 2
            ),
        },
        "block_io": {
            "read_bytes": disk_io.read_bytes if disk_io else 0,
            "write_bytes": disk_io.write_bytes if disk_io else 0,
            "read_mb": round((disk_io.read_bytes if disk_io else 0) / (1024 * 1024), 2),
            "write_mb": round(
                (disk_io.write_bytes if disk_io else 0) / (1024 * 1024), 2
            ),
            "read_delta_per_sec": round(
                disk_read_delta / config["app"]["websocket_update_interval"], 2
            ),
            "write_delta_per_sec": round(
                disk_write_delta / config["app"]["websocket_update_interval"], 2
            ),
        },
        "pids": num_threads,
    }


# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


class HTMLRequest(BaseModel):
    html: str = Field(..., description="HTML content to convert to PDF")
    use_cache: bool = Field(
        True, description="Whether to use cached results if available"
    )

    @field_validator("html")
    @classmethod
    def validate_html_size(cls, v: str) -> str:
        max_size_mb = config["optimization"]["max_html_size_mb"]
        max_size_bytes = max_size_mb * 1024 * 1024
        html_size = len(v.encode("utf-8"))

        if html_size > max_size_bytes:
            raise ValueError(
                f"HTML size ({html_size / 1024 / 1024:.2f}MB) exceeds maximum allowed size ({max_size_mb}MB)"
            )

        if not v.strip():
            raise ValueError("HTML content cannot be empty")

        return v

    class Config:
        json_schema_extra = {
            "example": {
                "html": "<html><body><h1>Hello World</h1><p>This is a test PDF.</p></body></html>",
                "use_cache": True,
            }
        }


@app.get("/", tags=["Health"])
async def root():
    """
    Health check endpoint
    """
    return {"message": "HTML to PDF API is running", "status": "healthy"}


@app.get("/config", tags=["Configuration"])
async def get_config():
    """
    Get current resource configuration
    """
    return config


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """
    Get Docker container metrics and API statistics (similar to Docker Desktop)
    """
    container_info = get_container_stats()
    uptime = datetime.now() - api_stats["start_time"]
    cache_stats = pdf_cache.stats()

    return {
        "container": container_info,
        "api": {
            "total_requests": api_stats["total_requests"],
            "successful_conversions": api_stats["successful_conversions"],
            "failed_conversions": api_stats["failed_conversions"],
            "cache_hits": api_stats["cache_hits"],
            "cache_misses": api_stats["cache_misses"],
            "cache_hit_rate": round(
                (api_stats["cache_hits"] / max(api_stats["total_requests"], 1)) * 100, 2
            ),
            "uptime_seconds": int(uptime.total_seconds()),
        },
        "cache": cache_stats,
    }


@app.get("/request-history", tags=["Monitoring"])
async def get_request_history():
    """
    Get history of recent PDF conversion requests with resource usage
    """
    return {"requests": request_history}


@app.post("/cache/clear", tags=["Cache Management"])
async def clear_cache():
    """
    Clear all cached PDFs
    """
    pdf_cache.clear()
    return {
        "message": "Cache cleared successfully",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/cache/stats", tags=["Cache Management"])
async def get_cache_stats():
    """
    Get detailed cache statistics
    """
    return {
        "cache": pdf_cache.stats(),
        "hit_rate": round(
            (api_stats["cache_hits"] / max(api_stats["total_requests"], 1)) * 100, 2
        ),
        "total_hits": api_stats["cache_hits"],
        "total_misses": api_stats["cache_misses"],
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Detailed health check with system status
    """
    process = _get_process()
    memory = psutil.virtual_memory()

    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": int(
            (datetime.now() - api_stats["start_time"]).total_seconds()
        ),
        "system": {
            "cpu_percent": psutil.cpu_percent(interval=0),
            "memory_percent": memory.percent,
            "memory_available_mb": round(memory.available / 1024 / 1024, 2),
        },
        "process": {
            "threads": process.num_threads(),
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 2),
        },
        "api": {
            "total_requests": api_stats["total_requests"],
            "success_rate": round(
                (
                    api_stats["successful_conversions"]
                    / max(api_stats["total_requests"], 1)
                )
                * 100,
                2,
            ),
        },
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time monitoring updates
    """
    await manager.connect(websocket)
    update_interval = config["app"]["websocket_update_interval"]

    try:
        while True:
            # Send container metrics using configured interval
            container_info = get_container_stats()
            uptime = datetime.now() - api_stats["start_time"]

            data = {
                "type": "metrics",
                "data": {
                    "container": container_info,
                    "api": {
                        "total_requests": api_stats["total_requests"],
                        "successful_conversions": api_stats["successful_conversions"],
                        "failed_conversions": api_stats["failed_conversions"],
                        "cache_hits": api_stats["cache_hits"],
                        "cache_misses": api_stats["cache_misses"],
                        "uptime_seconds": int(uptime.total_seconds()),
                    },
                    "timestamp": datetime.now().isoformat(),
                },
            }
            await websocket.send_json(data)
            await asyncio.sleep(update_interval)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Background task for periodic cleanup
@app.on_event("startup")
async def startup_event():
    """
    Background tasks on startup
    """
    asyncio.create_task(periodic_cleanup())


async def periodic_cleanup():
    """
    Periodic cleanup task to free resources
    """
    while True:
        await asyncio.sleep(300)  # Run every 5 minutes

        # Clean up old rate limiter entries
        rate_limiter.cleanup_old_entries()

        # Force garbage collection
        gc.collect()


@app.post("/convert/html-to-pdf", tags=["Conversion"], response_class=Response)
async def convert_html_to_pdf(request: HTMLRequest, http_request: Request):
    """
    Convert HTML content to PDF with caching and optimization

    - **html**: HTML string to convert to PDF
    - **use_cache**: Whether to use cached results (default: True)

    Returns a PDF file as binary content
    """
    # Rate limiting check
    client_id = http_request.client.host if http_request.client else "unknown"
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded. Please try again later."
        )

    api_stats["total_requests"] += 1

    # Check cache first if enabled
    if request.use_cache and config["optimization"]["cache_enabled"]:
        cached_pdf = pdf_cache.get(request.html)
        if cached_pdf:
            api_stats["cache_hits"] += 1
            api_stats["successful_conversions"] += 1

            # Record cache hit
            request_info = {
                "timestamp": datetime.now().isoformat(),
                "duration_seconds": 0.001,
                "status": "success_cached",
                "html_size_kb": round(len(request.html) / 1024, 2),
                "pdf_size_kb": round(len(cached_pdf) / 1024, 2),
                "cpu_usage_percent": 0,
                "memory_used_mb": 0,
                "system_memory_percent": 0,
            }
            request_history.append(request_info)
            if len(request_history) > MAX_HISTORY:
                request_history.pop(0)

            await manager.broadcast({"type": "new_request", "data": request_info})

            return Response(
                content=cached_pdf,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": "attachment; filename=output.pdf",
                    "X-Cache": "HIT",
                },
            )

    api_stats["cache_misses"] += 1

    # Record initial resource usage
    start_time = datetime.now()
    cpu_before = psutil.cpu_percent(interval=0)
    memory_before = psutil.virtual_memory()
    process = _get_process()
    process_memory_before = process.memory_info().rss

    try:
        # Lazy load WeasyPrint only when needed to save memory
        import weasyprint

        # Convert HTML to PDF using WeasyPrint with timeout
        timeout_seconds = config["optimization"]["conversion_timeout_seconds"]

        def convert_with_timeout() -> bytes:
            """Synchronous conversion function to run in thread pool"""
            html_doc = weasyprint.HTML(string=request.html)
            pdf_result = html_doc.write_pdf()
            del html_doc
            # write_pdf() can return bytes or None, handle both cases
            if pdf_result is None:
                raise ValueError("PDF generation returned None")
            return pdf_result

        try:
            pdf_bytes: bytes = await asyncio.wait_for(
                asyncio.to_thread(convert_with_timeout), timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            raise HTTPException(
                status_code=504,
                detail=f"PDF conversion timed out after {timeout_seconds} seconds",
            )

        # Force garbage collection to free memory
        gc.collect()

        # Cache the result if caching is enabled
        if request.use_cache and config["optimization"]["cache_enabled"]:
            pdf_cache.set(request.html, pdf_bytes)

        # Record final resource usage
        end_time = datetime.now()
        cpu_after = psutil.cpu_percent(interval=0)
        memory_after = psutil.virtual_memory()
        process_memory_after = process.memory_info().rss

        duration = (end_time - start_time).total_seconds()

        # Store request info
        request_info = {
            "timestamp": start_time.isoformat(),
            "duration_seconds": round(duration, 3),
            "status": "success",
            "html_size_kb": round(len(request.html) / 1024, 2),
            "pdf_size_kb": round(len(pdf_bytes) / 1024, 2),
            "cpu_usage_percent": round((cpu_before + cpu_after) / 2, 2),
            "memory_used_mb": round(
                (process_memory_after - process_memory_before) / (1024 * 1024), 2
            ),
            "system_memory_percent": round(memory_after.percent, 2),
        }

        request_history.append(request_info)
        # Keep only last 20 requests (reduced from 50)
        if len(request_history) > MAX_HISTORY:
            request_history.pop(0)

        api_stats["successful_conversions"] += 1

        # Broadcast new request to WebSocket clients
        await manager.broadcast({"type": "new_request", "data": request_info})

        # Return PDF as response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=output.pdf",
                "X-Cache": "MISS",
            },
        )
    except Exception as e:
        # Record failure
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        request_info = {
            "timestamp": start_time.isoformat(),
            "duration_seconds": round(duration, 3),
            "status": "failed",
            "html_size_kb": round(len(request.html) / 1024, 2),
            "pdf_size_kb": 0,
            "cpu_usage_percent": 0,
            "memory_used_mb": 0,
            "system_memory_percent": 0,
            "error": str(e),
        }

        request_history.append(request_info)
        if len(request_history) > MAX_HISTORY:
            request_history.pop(0)

        api_stats["failed_conversions"] += 1

        # Broadcast failed request to WebSocket clients
        await manager.broadcast({"type": "new_request", "data": request_info})

        raise HTTPException(
            status_code=500, detail=f"Error converting HTML to PDF: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
