# ==============================================================================
# Spider_XHS Multi-Stage Dockerfile
# ==============================================================================
# Stage 1: Build the frontend (React + Vite)
# Stage 2: Build the Python application with pre-built frontend assets
#
# Usage:
#   docker build -t spider-xhs .
#   docker run -p 8000:8000 -v ./data:/app/data -v ./config:/app/config spider-xhs
# ==============================================================================

# ---------------------------------------------------------------------------
# Stage 1: Frontend build
# ---------------------------------------------------------------------------
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend

# Install dependencies first (layer caching)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund

# Copy source and build
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Python application
# ---------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js runtime (required for JS signature execution)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source
COPY . .

# Copy pre-built frontend from Stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Install root-level Node.js deps (signature JS execution)
RUN if [ -f package.json ]; then npm install --no-audit --no-fund --omit=dev; fi

# Create data directory for SQLite and storage
RUN mkdir -p /app/data /app/backend/app/storage/media /app/backend/app/storage/exports

# Set environment defaults
ENV PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    FRONTEND_SERVE_STATIC=true \
    CONFIG_FILE=/app/config/default.yaml

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000"]
