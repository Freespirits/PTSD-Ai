# syntax=docker/dockerfile:1.7
FROM python:3.11-slim AS base

# System deps for PDF/audio handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    ffmpeg \
    libpq-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Application code
COPY agent/      ./agent/
COPY ingestion/  ./ingestion/

# Non-root for prod
RUN useradd -m -u 1000 ptsd && chown -R ptsd:ptsd /app
USER ptsd

# Default command - override in docker-compose
CMD ["python", "-m", "agent.main", "start"]
