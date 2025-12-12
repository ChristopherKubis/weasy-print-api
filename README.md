# HTML to PDF API

A FastAPI application that converts HTML content to PDF using WeasyPrint.

## Features

- Convert HTML to PDF via REST API
- Interactive Swagger UI documentation
- Easy to deploy and extend
- Production-ready Docker container

## Setup

### Option 1: Docker (Recommended - Works on all platforms)

```bash
docker-compose up --build
```

Access at http://localhost:8000/docs

### Option 2: Local Development

⚠️ **IMPORTANT FOR WINDOWS**: WeasyPrint requires GTK libraries that are not installed by default.

**For Windows:**
1. **Install GTK3 Runtime**: Download and install from https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
   - Run the installer `gtk3-runtime-x.x.x-x-x-x-ts-win64.exe`
   - Restart your terminal after installation
2. **Add GTK to PATH** (if needed): `C:\Program Files\GTK3-Runtime Win64\bin`

**After installing GTK (or on Linux/Mac):**

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python main.py
```

Or using uvicorn directly:
```bash
uvicorn main:app --reload
```

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

### Build and run with Docker Compose:
```bash
docker-compose up --build
```

### Or build and run manually:
```bash
# Build the image
docker build -t weasy-print-api .

# Run the container
docker run -d -p 8000:8000 --name weasy-print-api weasy-print-api
```

### Access the API:
- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/
