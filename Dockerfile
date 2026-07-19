# Production multi-stage build: Python API (FastAPI) + Node.js frontend (vinext)
#
# Architecture:
#   - Python 3.14 backend on :8000
#   - Node.js 24 frontend on :3000
#   - Single container with signal-aware entrypoint
#   - SQLite database under /data
#   - Runs as non-root user (postbox)

# ============================================================================
# Stage 1: Python API Builder
# ============================================================================

FROM python:3.14-slim AS python-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

WORKDIR /app

# Install Poetry (pinned version for reproducibility)
RUN pip install --no-cache-dir "poetry>=1.7.0,<2.0"

# Copy dependency manifests and metadata first for layer caching
# README.md is required by pyproject.toml (readme = "README.md")
COPY pyproject.toml poetry.lock README.md ./

# Copy Python source (required by Poetry to discover the package)
COPY src ./src

# Copy migrations (required at runtime)
COPY migrations ./migrations

# Install production dependencies and the root package
RUN poetry install --only main --no-interaction --no-ansi

# ============================================================================
# Stage 2: Node.js Frontend Builder
# ============================================================================

FROM node:24-alpine AS node-builder

WORKDIR /app/web

# Copy dependency manifests
COPY web/package.json web/package-lock.json ./

# Install ALL dependencies (including dev) required for production build
# Note: DO NOT use --omit=dev; vinext build requires build-time dev dependencies
RUN npm ci

# Copy complete frontend source, including:
#   - vite.config.ts and its imports (e.g., web/build/sites-vite-plugin.ts)
#   - app/ directory
#   - public/ directory
#   - all other tracked source files
COPY web ./

# Build frontend
RUN npm run build

# ============================================================================
# Stage 3: Production Runtime
# ============================================================================

FROM node:24-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    NODE_ENV=production

WORKDIR /app

# Install Python runtime and required build dependencies
# curl: required for Docker healthcheck
# build-base: required if any Python packages need compilation
RUN apk add --no-cache \
    python3 \
    py3-pip \
    curl \
    build-base

# ============================================================================
# Copy Python artifacts from builder
# ============================================================================

# Copy installed Python dependencies and the postbox package
COPY --from=python-builder /app/src ./src
COPY --from=python-builder /app/migrations ./migrations
COPY --from=python-builder /app/pyproject.toml .
COPY --from=python-builder /app/poetry.lock .
COPY --from=python-builder /app/README.md .

# Poetry installed packages are in site-packages (via POETRY_VIRTUALENVS_CREATE=false)
# which are in the system Python. Since we're using the same Python image,
# pip should have installed them in /usr/local/lib/python3.xx/site-packages

# ============================================================================
# Copy Node.js artifacts from builder
# ============================================================================

# Copy only the built frontend output (not full node_modules from builder)
# vinext build output goes to .next and dist directories
COPY --from=node-builder /app/web/package*.json ./web/
COPY --from=node-builder /app/web/.next ./web/.next
COPY --from=node-builder /app/web/dist ./web/dist
COPY --from=node-builder /app/web/public ./web/public

# Copy node_modules only runtime dependencies (use npm prune to reduce size)
# Install only production dependencies in the runtime stage
WORKDIR /app/web
RUN npm ci --omit=dev
WORKDIR /app

# ============================================================================
# Setup runtime
# ============================================================================

# Create non-root user and persistent data directory
RUN adduser -D -u 10001 postbox && \
    mkdir -p /data && \
    chown -R postbox:postbox /app /data

# Copy startup script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && \
    chown postbox:postbox /usr/local/bin/docker-entrypoint.sh

# ============================================================================
# Final container configuration
# ============================================================================

USER postbox
WORKDIR /app

# Expose internal ports (reverse proxy external)
EXPOSE 3000 8000

# Healthcheck: verify API responds
HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=10s \
    CMD curl --fail http://127.0.0.1:8000/api/ready || exit 1

# Start both services with signal handling
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
