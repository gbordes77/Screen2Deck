# Multi-arch build support (amd64, arm64)
ARG TARGETPLATFORM
ARG BUILDPLATFORM
ARG TARGETARCH

FROM --platform=$TARGETPLATFORM python:3.11-slim

# Build arguments
ARG VERSION=2.0.0
ARG BUILD_DATE
ARG VCS_REF

# Labels for metadata
LABEL org.opencontainers.image.title="Screen2Deck Backend" \
      org.opencontainers.image.description="Production-ready OCR for MTG decks" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/gbordes77/Screen2Deck" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.vendor="Screen2Deck" \
      org.opencontainers.image.licenses="MIT"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TARGETARCH=${TARGETARCH}

# Install system dependencies (including libmagic for python-magic)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgl1 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and group
RUN groupadd -r screen2deck && \
    useradd -r -g screen2deck -d /app -s /sbin/nologin screen2deck

# Create app directory and set ownership
WORKDIR /app
RUN chown -R screen2deck:screen2deck /app

# Copy requirements first for better caching
COPY --chown=screen2deck:screen2deck requirements.txt ./

# Switch to non-root user for pip install
USER screen2deck

# Install Python dependencies
RUN pip install --user --no-cache-dir -r requirements.txt

# Pre-download EasyOCR models for faster cold starts (English only)
# This adds ~700MB to image but eliminates runtime download
RUN python -c "import easyocr; easyocr.Reader(['en'], gpu=False, verbose=False)" || true

# Copy application code
COPY --chown=screen2deck:screen2deck app ./app
COPY --chown=screen2deck:screen2deck scripts ./scripts

# Create data directory for Scryfall cache
RUN mkdir -p ./app/data

# Expose port (non-privileged)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run as non-root user
USER screen2deck

# Auto-hydrate Scryfall on first run; then start API
CMD bash -lc 'if [ ! -f ./app/data/scryfall-default-cards.json ]; then python scripts/download_scryfall.py; fi; python -m uvicorn app.main:app --host 0.0.0.0 --port 8080'