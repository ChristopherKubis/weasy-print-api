# WeasyPrint API - Start Script
# This script generates docker-compose.yml from config.yml and starts the containers

Write-Host "🚀 WeasyPrint API Startup Script" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan
Write-Host ""

# Check if config.yml exists
if (-not (Test-Path "backend/config.yml")) {
    Write-Host "❌ Error: backend/config.yml not found!" -ForegroundColor Red
    Write-Host "Please create config.yml with resource limits." -ForegroundColor Yellow
    exit 1
}

# Generate docker-compose.yml from config.yml
Write-Host "📝 Generating docker-compose.yml from config.yml..." -ForegroundColor Yellow
python backend/load_docker_config.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to generate docker-compose.yml" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Stop existing containers
Write-Host "🛑 Stopping existing containers..." -ForegroundColor Yellow
docker-compose down

Write-Host ""

# Start containers
Write-Host "🔨 Building and starting containers..." -ForegroundColor Green
docker-compose up --build

Write-Host ""
Write-Host "✅ Done!" -ForegroundColor Green
