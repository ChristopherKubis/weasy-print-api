# Use minidocks/weasyprint - the lightest WeasyPrint image available
FROM minidocks/weasyprint:latest

# Set working directory
WORKDIR /app

# Install build dependencies first
RUN apk add --no-cache gcc musl-dev python3-dev libffi-dev

# Copy requirements file first for better caching
COPY requirements.txt .

# Install additional Python dependencies (WeasyPrint already included)
# Use --break-system-packages for Alpine Linux managed environment
RUN pip install --no-cache-dir --break-system-packages --upgrade pip && \
    pip install --no-cache-dir --break-system-packages -r requirements.txt

# Copy configuration and application code
COPY config.yml .
COPY main.py .

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
