#!/usr/bin/env python3
"""
Script to load config.yml and generate docker-compose.yml with resource limits
"""
import yaml
import os


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yml")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def generate_docker_compose(config):
    api_mem_limit = f"{config['resources']['memory']['limit_gb']}g"
    api_mem_reservation = f"{config['resources']['memory']['reservation_mb']}m"
    api_cpu_limit = str(config["resources"]["cpu"]["limit_cores"])
    api_cpu_reservation = str(config["resources"]["cpu"]["reservation_cores"])

    frontend_mem_limit = f"{config['frontend']['memory']['limit_mb']}m"
    frontend_cpu_limit = str(config["frontend"]["cpu"]["limit_cores"])

    docker_compose = f"""version: '3.8'

services:
  weasyprint-api:
    build: ./backend
    container_name: weasyprint-api
    ports:
      - "8000:8000"
    volumes:
      - ./backend/config.yml:/app/config.yml:ro
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    mem_limit: {api_mem_limit}
    mem_reservation: {api_mem_reservation}
    cpus: '{api_cpu_limit}'
    cpu_shares: 1024
    deploy:
      resources:
        limits:
          cpus: '{api_cpu_limit}'
          memory: {api_mem_limit}
        reservations:
          cpus: '{api_cpu_reservation}'
          memory: {api_mem_reservation}
    networks:
      - weasyprint-network

  frontend:
    build: ./frontend
    container_name: weasyprint-frontend
    ports:
      - "3000:80"
    depends_on:
      - weasyprint-api
    restart: unless-stopped
    mem_limit: {frontend_mem_limit}
    cpus: '{frontend_cpu_limit}'
    deploy:
      resources:
        limits:
          cpus: '{frontend_cpu_limit}'
          memory: {frontend_mem_limit}
        reservations:
          cpus: '0.25'
          memory: 128m
    networks:
      - weasyprint-network

networks:
  weasyprint-network:
    driver: bridge
"""

    with open("docker-compose.yml", "w") as f:
        f.write(docker_compose)

    print("✅ docker-compose.yml generated successfully!")
    print(
        f"   API: {api_cpu_limit} CPUs ({api_cpu_reservation} reserved), {api_mem_limit} RAM ({api_mem_reservation} reserved)"
    )
    print(f"   Frontend: {frontend_cpu_limit} CPUs, {frontend_mem_limit} RAM")


if __name__ == "__main__":
    try:
        config = load_config()
        # Change to parent directory to write docker-compose.yml in root
        import os
        os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        generate_docker_compose(config)
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)
