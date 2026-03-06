FROM python:3.11-slim

LABEL maintainer="Auto Video Engine"
LABEL description="AI-powered movie video generation pipeline"

# System deps: FFmpeg + yt-dlp runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Create runtime directories
RUN mkdir -p media temp output assets/fonts assets/music assets/sfx

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default: run the API server
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
