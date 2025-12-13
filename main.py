from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psutil
import io
import json
import asyncio
import yaml
from datetime import datetime
from typing import List, Optional
import gc
import os

# Load configuration from config.yml
with open("config.yml", "r") as f:
    config = yaml.safe_load(f)

# Don't import weasyprint at startup - lazy load when needed to save memory

app = FastAPI(
    title="HTML to PDF API",
    description="API to convert HTML content to PDF using WeasyPrint",
    version="1.0.0",
)

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


def get_container_stats():
    """Get Docker container statistics similar to Docker Desktop"""
    process = psutil.Process()

    # CPU usage
    cpu_percent = process.cpu_percent(interval=0.1)

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
    html: str

    class Config:
        json_schema_extra = {
            "example": {
                "html": "<html><body><h1>Hello World</h1><p>This is a test PDF.</p></body></html>"
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

    return {
        "container": container_info,
        "api": {
            "total_requests": api_stats["total_requests"],
            "successful_conversions": api_stats["successful_conversions"],
            "failed_conversions": api_stats["failed_conversions"],
            "uptime_seconds": int(uptime.total_seconds()),
        },
    }


@app.get("/request-history", tags=["Monitoring"])
async def get_request_history():
    """
    Get history of recent PDF conversion requests with resource usage
    """
    return {"requests": request_history}


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
                        "uptime_seconds": int(uptime.total_seconds()),
                    },
                    "timestamp": datetime.now().isoformat(),
                },
            }
            await websocket.send_json(data)
            await asyncio.sleep(update_interval)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/convert/html-to-pdf", tags=["Conversion"], response_class=Response)
async def convert_html_to_pdf(request: HTMLRequest):
    """
    Convert HTML content to PDF

    - **html**: HTML string to convert to PDF

    Returns a PDF file as binary content
    """
    api_stats["total_requests"] += 1

    # Record initial resource usage
    start_time = datetime.now()
    cpu_before = psutil.cpu_percent(interval=0.1)
    memory_before = psutil.virtual_memory()
    process = psutil.Process()
    process_memory_before = process.memory_info().rss

    try:
        # Lazy load WeasyPrint only when needed to save memory
        import weasyprint

        # Convert HTML to PDF using WeasyPrint
        html_doc = weasyprint.HTML(string=request.html)
        pdf_bytes = html_doc.write_pdf()

        # Force garbage collection to free memory
        del html_doc
        gc.collect()

        # Record final resource usage
        end_time = datetime.now()
        cpu_after = psutil.cpu_percent(interval=0.1)
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
            headers={"Content-Disposition": "attachment; filename=output.pdf"},
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
