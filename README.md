# HTML to PDF API

A FastAPI application that converts HTML content to PDF using WeasyPrint with real-time Docker container monitoring.

## Features

- 🖨️ Convert HTML to PDF via REST API
- 📊 Real-time container monitoring dashboard (Docker Desktop style)
- 🐳 Centralized resource configuration (CPU/Memory limits)
- 📈 WebSocket live metrics (CPU, Memory, Network I/O, Block I/O)
- 📝 Request history with resource usage tracking
- 🔧 Interactive Swagger UI documentation
- ⚙️ Easy resource management via config.yml
- 🚀 Production-ready Docker container with minidocks/weasyprint

## Quick Start

### Using the automated startup script (Recommended)

The application uses a centralized configuration file (`config.yml`) for resource management.

```powershell
# Windows PowerShell
.\start.ps1
```

```bash
# Linux/Mac
./start.sh
```

This script will:
1. Load `config.yml` and generate `docker-compose.yml` with resource limits
2. Build and start the containers automatically

Access the services:
- **Monitoring Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Configuration Endpoint**: http://localhost:8000/config

### Manual Docker setup

```bash
# Generate docker-compose.yml from config.yml
python load_docker_config.py

# Start containers
docker-compose up --build
```

### Option 2: Local Development

⚠️ **IMPORTANT FOR WINDOWS**: WeasyPrint requires GTK libraries that are not installed by default.

## Resource Configuration

Edit `config.yml` to control CPU and memory limits:

```yaml
resources:
  memory:
    limit_gb: 2              # Maximum memory for API container
    reservation_mb: 512      # Reserved memory
  cpu:
    limit_cores: 2.0         # Maximum CPU cores
    reservation_cores: 0.5   # Reserved CPU cores
  
app:
  websocket_update_interval: 5  # Metrics update frequency (seconds)
  request_history_max: 20       # Number of requests to keep in history

frontend:
  memory:
    limit_mb: 512           # Frontend memory limit
  cpu:
    limit_cores: 1.0        # Frontend CPU limit
```

After changing `config.yml`, restart with:
```powershell
.\start.ps1
```

## API Documentation

Once running, access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Current Config**: http://localhost:8000/config

## Endpoints

### GET /
Health check endpoint

**Response:**
```json
{
  "message": "HTML to PDF API is running",
  "status": "healthy"
}
```
## Monitoring Dashboard

Access the real-time monitoring dashboard at http://localhost:3000

**Features:**
- 🐳 Docker container stats (CPU, Memory, Network, Disk I/O)
- 📊 Live charts with historical data (last 100 seconds)
- 📈 Real-time WebSocket updates (no polling)
- 📝 Recent conversion requests with resource usage
- ✅ API health status
- 🔄 Automatic reconnection on disconnect

**Dashboard displays:**
- Container CPU usage (% of configured limit)
- Memory usage (% of 2GB limit)
- Network I/O (RX/TX bytes per second)
- Block I/O (Read/Write bytes per second)
- API statistics (total requests, success/failure rates)
- Detailed request history with resource consumption

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   config.yml                    │
│  (Single source of truth for resource limits)  │
└───────────────┬─────────────────────────────────┘
                │
                ├─→ load_docker_config.py
                │   (Generates docker-compose.yml)
                │
                ├─→ main.py (FastAPI)
                │   (Loads config for memory calculations)
                │
                └─→ Dockerfile
                    (Copies config.yml to container)

┌─────────────────┐      ┌──────────────────┐
│  Container API  │◄────►│  Frontend React  │
│  (Port 8000)    │ WS   │  (Port 3000)     │
│                 │      │                  │
│ - FastAPI       │      │ - Real-time      │
│ - WeasyPrint    │      │   Dashboard      │
│ - WebSocket     │      │ - Recharts       │
│ - psutil        │      │ - Axios          │
└─────────────────┘      └──────────────────┘
```

## Resource Optimization

The application uses several techniques to minimize resource usage:

1. **Lazy Loading**: WeasyPrint is imported only when needed
2. **Garbage Collection**: Forced cleanup after each PDF generation
3. **Memory Limits**: Docker enforces 2GB limit (configurable)
4. **CPU Limits**: Docker enforces 2 cores limit (configurable)
5. **Efficient WebSocket**: Updates every 5 seconds (configurable)
6. **Limited History**: Keeps only last 20 requests (configurable)
7. **Lightweight Base**: Uses minidocks/weasyprint (~100MB image)

## Development

### VS Code Debugging

Use the provided launch configuration to debug the application (F5).

### Local Development (without Docker)

⚠️ **IMPORTANT FOR WINDOWS**: WeasyPrint requires GTK libraries.

1. Install GTK3 Runtime: https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Run locally:
```bash
python main.py
```

### Project Structure

```
weasy-print-api/
├── config.yml              # Resource configuration (EDIT THIS!)
├── load_docker_config.py   # Generates docker-compose.yml
├── start.ps1              # Startup script (Windows)
├── main.py                # FastAPI application
├── requirements.txt       # Python dependencies
├── Dockerfile             # API container definition
├── docker-compose.yml     # Generated automatically
├── .vscode/
│   └── launch.json       # VS Code debug config
└── frontend/
    ├── src/
    │   ├── App.js        # React monitoring dashboard
    │   └── App.css       # Dashboard styles
    ├── Dockerfile        # Frontend container
    └── package.json      # Node dependencies
```

## Docker

### Resource Limits

Docker Desktop shows CPU usage relative to the **configured limit**:
- 100% = using all 2 cores allowed
- 50% = using 1 core of the 2 allowed

The `docker stats` CLI command shows usage relative to **total system cores**.

### Manual Docker Commands

```bash
# Generate docker-compose.yml from config.yml
python load_docker_config.py

# Start services
docker-compose up --build

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# View specific container logs
docker logs weasyprint-api -f
```

## Technologies Used

**Backend:**
- FastAPI 0.104.1 - Modern Python web framework
- WeasyPrint 67.0 - HTML to PDF conversion
- psutil 5.9.6 - System resource monitoring
- PyYAML 6.0.1 - Configuration file parsing
- WebSockets 12.0 - Real-time communication
- Uvicorn 0.24.0 - ASGI server

**Frontend:**
- React 18 - UI framework
- Recharts - Data visualization
- Axios - HTTP client
- WebSocket API - Real-time updates

**Infrastructure:**
- Docker - Containerization
- minidocks/weasyprint - Optimized base image (~100MB)
- Nginx Alpine - Frontend web servercores": 2.0},
    "memory": {
      "used_mb": 245.5,
      "limit_gb": 2,
      "percent_of_limit": 12.3
    },
    "network": {"rx_mb": 1.5, "tx_mb": 0.8},
    "block_io": {"read_mb": 10.2, "write_mb": 5.4}
  },
  "api": {
    "total_requests": 42,
    "successful_conversions": 40,
    "failed_conversions": 2,
    "uptime_seconds": 3600
  }
}
```

### GET /request-history
Get history of recent PDF conversion requests with resource usage

**Response:**
```json
{
  "requests": [
    {
      "timestamp": "2025-12-13T10:30:15.123456",
      "duration_seconds": 0.856,
      "status": "success",
      "html_size_kb": 12.5,
      "pdf_size_kb": 45.2,
      "cpu_usage_percent": 18.5,
      "memory_used_mb": 23.4,
      "system_memory_percent": 1.2
    }
  ]
}
```

### WebSocket /ws
Real-time container metrics updates (every 5 seconds by default)

**Connection:** `ws://localhost:8000/ws`

**Message format:**
```json
{
  "type": "metrics",
  "data": {
    "container": { /* same as /metrics */ },
    "api": { /* same as /metrics */ },
    "timestamp": "2025-12-13T10:30:15.123456"
  }
}
```

### POST /convert/html-to-pdf
Convert HTML content to PDF

**Request Body:**
```json
{
  "html": "<html><body><h1>Hello World</h1></body></html>"
}
```

**Response:** PDF file (application/pdf)

**💡 Recommendation**: Use Docker to avoid system dependencies issues!

## API Documentation

Once running, access:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Endpoints

### GET /
Health check endpoint

### POST /convert/html-to-pdf
Convert HTML content to PDF

**Request Body:**
```json
{
  "html": "<html><body><h1>Hello World</h1></body></html>"
}
```

**Response:** PDF file (application/pdf)

## Development

Use VS Code with the provided launch configuration to debug the application (F5).

## Docker

### Build and run with Docker Compose (API + Frontend):
```bash
docker-compose up --build
```

This will start:
- **API**: http://localhost:8000
- **Monitoring Dashboard**: http://localhost:3000

### Or build and run manually:
```bash
# Build the API image
docker build -t weasyprint-api .

# Run the API container
docker run -d -p 8000:8000 --name weasyprint-api weasyprint-api
```

### Access the services:
- **Monitoring Dashboard**: http://localhost:3000
- **API Swagger UI**: http://localhost:8000/docs
- **API Health check**: http://localhost:8000/
- **API Metrics**: http://localhost:8000/metrics
