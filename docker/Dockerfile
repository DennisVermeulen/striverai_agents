# Stage 1: Build frontend
FROM node:22-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Python runtime
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

ENV DEBIAN_FRONTEND=noninteractive

# Install display server, VNC, window manager, and supervisord
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    fluxbox \
    supervisor \
    novnc \
    websockify \
    python3.12-venv \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Create a venv to avoid conflicts with system-managed Python packages
RUN python -m venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy project files
COPY pyproject.toml .
COPY src/ src/
COPY cli/ cli/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Install Playwright browsers (already present in base image, but ensure chromium)
RUN playwright install chromium

# Copy built frontend from stage 1
COPY --from=frontend-build /build/dist/ frontend/dist/

# Copy Docker-specific configs
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Data directories
RUN mkdir -p /app/data/sessions /app/data/screenshots /app/data/logs /app/data/workflows

# Ports: API, VNC, noVNC
EXPOSE 8000 5900 6080

# Environment defaults
ENV DISPLAY=:99
ENV DISPLAY_NUM=99
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

ENTRYPOINT ["/entrypoint.sh"]
