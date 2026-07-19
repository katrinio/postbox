# Multi-stage build: Python API + Node.js Web

# Stage 1: Python API
FROM python:3.14-slim AS api-builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONPATH=/app/src

WORKDIR /app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./
COPY src ./src

RUN poetry install --only main

# Stage 2: Node.js Web
FROM node:24-alpine AS web-builder

WORKDIR /app/web

COPY web/package*.json ./
RUN npm ci --omit=dev

COPY web ./

RUN npm run build

# Stage 3: Production runtime (based on Node.js 24 for consistency)
FROM node:24-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    NODE_ENV=production

WORKDIR /app

# Install Python runtime
RUN apk add --no-cache python3 py3-pip

# Copy Python dependencies from builder
COPY --from=api-builder /app ./

# Copy Node.js app from builder
COPY --from=web-builder /app/web ./web

# Create app user
RUN useradd --create-home --uid 10001 postbox && \
    mkdir -p /data && \
    chown -R postbox:postbox /app /data

USER postbox

EXPOSE 3000 8000

# Copy entrypoint script
COPY --chown=postbox:postbox docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
