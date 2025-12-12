from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import weasyprint
import psutil
import io
import json
import asyncio
from datetime import datetime
from typing import List

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

# Request History (keep last 50 requests)
request_history = []


# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


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


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """
    Get system metrics and API statistics
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()

    uptime = datetime.now() - api_stats["start_time"]

    return {
        "cpu": {"percent": cpu_percent, "count": psutil.cpu_count()},
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percent": memory.percent,
        },
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
    try:
        while True:
            # Send metrics every 2 seconds
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            uptime = datetime.now() - api_stats["start_time"]

            data = {
                "type": "metrics",
                "data": {
                    "cpu": {"percent": cpu_percent, "count": psutil.cpu_count()},
                    "memory": {
                        "total": memory.total,
                        "available": memory.available,
                        "used": memory.used,
                        "percent": memory.percent,
                    },
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
            await asyncio.sleep(2)
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
        # Convert HTML to PDF using WeasyPrint
        html_doc = weasyprint.HTML(string=request.html)
        pdf_bytes = html_doc.write_pdf()

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
        # Keep only last 50 requests
        if len(request_history) > 50:
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
        if len(request_history) > 50:
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
