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
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry>=2.0,<3.0"

# Copy metadata and source for build.
COPY pyproject.toml poetry.lock README.md ./
COPY src ./src

# Build the wheel.
RUN poetry build --format wheel && \
    wheel_file=$(ls dist/postbox-*.whl | head -1) && \
    test -n "$wheel_file" || (echo "ERROR: No wheel produced"; exit 1) && \
    echo "✓ Built wheel: $wheel_file"

# Create a clean virtual environment and install the wheel with its dependencies.
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir \
        dist/postbox-*.whl && \
    echo "✓ Installed wheel into /opt/venv"

# Validate the installation: import postbox from outside /app, verify paths.
RUN cd /tmp && \
    /opt/venv/bin/python -c "
import postbox
import postbox.api
postbox_path = postbox.__file__
if '/opt/venv' not in postbox_path:
    print(f'ERROR: postbox resolved to {postbox_path}, not /opt/venv')
    exit(1)
print(f'✓ postbox imports successfully from /opt/venv')
print(f'✓ postbox.__file__ = {postbox_path}')
" && \
    test -x /opt/venv/bin/postbox-api && \
    echo "✓ postbox-api console script installed and executable"

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

# Copy the built virtual environment.
# It is completely autonomous: contains the wheel-installed postbox package
# and all its dependencies, with no references to the builder filesystem.
COPY --from=python-builder /opt/venv /opt/venv

# Copy only runtime-required data files (not source).
# These are external resources needed at runtime, kept separate from the wheel.
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

# Validate Python runtime: verify postbox is installed in /opt/venv and autonomous.
RUN command -v postbox-api && \
    /opt/venv/bin/python -c "
import postbox
import postbox.api
# Verify package path is in /opt/venv, not sourced from the repo.
postbox_path = postbox.__file__
if '/opt/venv' not in postbox_path:
    print(f'ERROR: postbox resolved to {postbox_path}, not /opt/venv')
    exit(1)
print(f'✓ postbox is autonomous in /opt/venv')
" && \
    echo "✓ Python runtime is valid"

# Validate Node.js and frontend.
RUN node --version && \
    npm --version && \
    npm list vinext 2>/dev/null | grep vinext && \
    test -f /app/web/dist/server/index.js && \
    echo "✓ Node.js runtime is valid"


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
