# syntax=docker/dockerfile:1
FROM python:3.13-slim

# Install system dependencies (if any are needed in future, keep minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
 && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Leverage Docker layer caching: copy just requirements first
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Default environment (can be overridden at runtime)
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SIGEN_TOKEN_FILE=/data/sigen_token.json \
    LOG_LEVEL=INFO

# Create a mount point for persistent data (token, logs)
VOLUME ["/data"]

# Runtime command is configurable via CMD (scheduler by default)
CMD ["python", "main_scheduler.py"]
