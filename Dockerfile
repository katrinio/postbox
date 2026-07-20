# Production multi-stage build:
# Python API (FastAPI) + Node.js frontend (vinext)
#
# Architecture:
#   - Python 3.14 backend on :8000
#   - Node.js 24 frontend on :3000
#   - Single container with signal-aware entrypoint
#   - SQLite database under /data
#   - Runs as non-root user (postbox)

# ============================================================================
# Stage 1: Python API builder
# ============================================================================

FROM python:3.14-slim AS python-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_VIRTUALENVS_IN_PROJECT=true

WORKDIR /app

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry>=2.0,<3.0"

COPY pyproject.toml poetry.lock README.md ./
COPY src ./src

RUN poetry install \
        --only main \
        --no-interaction \
        --no-ansi && \
    test -x /app/.venv/bin/postbox-api

# ============================================================================
# Stage 2: Node.js frontend builder
# ============================================================================

FROM node:24-bookworm-slim AS node-builder

ENV NODE_ENV=development

WORKDIR /app/web

# Copy dependency manifests first for Docker layer caching.
COPY web/package.json web/package-lock.json ./

# Install all dependencies required for the production build.
RUN npm ci

# Copy the complete frontend source.
COPY web ./

# Build the vinext frontend.
RUN npm run build

# Verify expected vinext runtime output.
RUN test -f /app/web/dist/server/index.js


# ============================================================================
# Stage 3: Production runtime
# ============================================================================

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    PATH="/opt/venv/bin:/usr/local/bin:${PATH}"

WORKDIR /app

# Install only runtime system packages.
# curl is used by the Docker healthcheck.
RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        ca-certificates \
        curl && \
    rm -rf /var/lib/apt/lists/*

# ============================================================================
# Copy Python runtime
# ============================================================================

# Copy the complete virtual environment.
# This includes:
#   - production dependencies
#   - the installed Postbox package
#   - the postbox-api console command
COPY --from=python-builder /app/.venv /opt/venv

# Copy runtime application files.
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini


# ============================================================================
# Copy Node.js runtime
# ============================================================================

# Copy Node.js binaries from the Debian-based builder image.
# Both builder and runtime are Debian-based, avoiding Alpine/glibc issues.
COPY --from=node-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=node-builder /usr/local/bin/npm /usr/local/bin/npm
COPY --from=node-builder /usr/local/bin/npx /usr/local/bin/npx

# Copy the built frontend.
# node_modules is copied below with Node.js binaries (required by npm start).
COPY --from=node-builder /app/web/dist ./web/dist
COPY --from=node-builder /app/web/node_modules ./web/node_modules


# ============================================================================
# Runtime setup
# ============================================================================

# Create a non-root user and the persistent SQLite data directory.
RUN useradd \
        --create-home \
        --uid 10001 \
        --shell /usr/sbin/nologin \
        postbox && \
    mkdir -p /data && \
    chown -R postbox:postbox /app /data /opt/venv

# Copy the signal-aware startup script.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh && \
    chown postbox:postbox /usr/local/bin/docker-entrypoint.sh

# Validate that all runtime dependencies are available and functional.
RUN command -v postbox-api && \
    python -c "import postbox; print(f'✓ postbox package imports successfully')" && \
    node --version && \
    npm --version && \
    npm list vinext 2>/dev/null | grep vinext && \
    test -f /app/web/dist/server/index.js && echo "✓ Frontend bundled server exists"


# ============================================================================
# Final container configuration
# ============================================================================

USER postbox
WORKDIR /app

EXPOSE 3000 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --retries=3 \
    --start-period=15s \
    CMD curl --fail --silent http://127.0.0.1:8000/api/ready && \
        curl --fail --silent http://127.0.0.1:3000/ >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
