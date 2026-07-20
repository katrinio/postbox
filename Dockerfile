# Postbox: Python API + Vinext frontend
#   API: FastAPI on :8000
#   Frontend: Vinext (Next.js for Cloudflare Workers) on :3000
#   Database: SQLite under /data
#   User: postbox (non-root)

# ============================================================================
# python-builder: Build autonomous Python runtime
# ============================================================================

FROM python:3.14-slim AS python-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1

WORKDIR /app

RUN apt-get update && \
    apt-get install --yes --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "poetry>=2.0,<3.0"

COPY pyproject.toml poetry.lock README.md ./
COPY src ./src

RUN poetry build --format wheel && \
    wheel_file=$(ls dist/postbox-*.whl | head -1) && \
    test -n "$wheel_file" || (echo "ERROR: No wheel produced"; exit 1)

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir dist/postbox-*.whl

RUN cd /tmp && \
    /opt/venv/bin/python -c "
import postbox
import postbox.api
if '/opt/venv' not in postbox.__file__:
    exit(1)
" && test -x /opt/venv/bin/postbox-api

# ============================================================================
# node-builder: Build frontend production artifact
# ============================================================================

FROM node:24-bookworm-slim AS node-builder

ENV NODE_ENV=development

WORKDIR /app/web

COPY web/package.json web/package-lock.json ./

RUN npm ci

COPY web ./

RUN npm run build

RUN test -f /app/web/dist/server/index.js && \
    test -d /app/web/dist/client && \
    test -d /app/web/dist/.openai && \
    test -x /app/web/node_modules/.bin/vinext


# ============================================================================
# runtime: Assemble production image
# ============================================================================

FROM python:3.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NODE_ENV=production \
    PATH="/opt/venv/bin:/usr/local/bin:${PATH}"

WORKDIR /app

RUN apt-get update && \
    apt-get install --yes --no-install-recommends \
        ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Copy Python runtime artifact from builder
COPY --from=python-builder /opt/venv /opt/venv

# Copy Python runtime data files
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini

# Copy Node.js runtime (from Debian-based builder to Debian-based runtime)
COPY --from=node-builder /usr/local/bin/node /usr/local/bin/node
COPY --from=node-builder /usr/local/bin/npm /usr/local/bin/npm
COPY --from=node-builder /usr/local/bin/npx /usr/local/bin/npx

# Copy frontend production artifact
COPY --from=node-builder /app/web/package.json ./web/package.json
COPY --from=node-builder /app/web/package-lock.json ./web/package-lock.json
COPY --from=node-builder /app/web/dist ./web/dist
COPY --from=node-builder /app/web/node_modules ./web/node_modules

# Create application user and data directory
RUN useradd \
        --create-home \
        --uid 10001 \
        --shell /usr/sbin/nologin \
        postbox && \
    mkdir -p /data && \
    chown -R postbox:postbox /app /data /opt/venv

# Copy and set up entrypoint
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh && \
    chown postbox:postbox /usr/local/bin/docker-entrypoint.sh

# Smoke check: verify runtime commands exist
RUN command -v postbox-api && \
    command -v npm && \
    test -d /app/web/dist/server && \
    test -d /app/web/dist/client

# Switch to unprivileged user
USER postbox

EXPOSE 3000 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --retries=3 \
    --start-period=15s \
    CMD curl --fail --silent http://127.0.0.1:8000/api/ready && \
        curl --fail --silent http://127.0.0.1:3000/ >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
