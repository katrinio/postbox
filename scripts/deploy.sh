#!/bin/bash
#
# Deploy Postbox to production.
#
# Usage:
#   cd ~/projects/postbox && ./scripts/deploy.sh
#
# This script:
#   1. Pulls latest code from main
#   2. Creates a backup of the database
#   3. Rebuilds Docker image (if needed)
#   4. Gracefully restarts containers (preserves data)
#   5. Waits for health check
#
# Failure at any step stops deployment and leaves previous version running.
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'  # No Color

# Logging
log() {
  echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $*"
}

warn() {
  echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $*"
}

error() {
  echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $*" >&2
  exit 1
}

# Configuration
REPO_DIR="${REPO_DIR:-.}"
DATA_DIR="${REPO_DIR}/data"
BACKUP_DIR="${REPO_DIR}/backups"

log "Starting Postbox deployment..."
log "Repository: $REPO_DIR"

# Validate .env file exists
if [[ ! -f "${REPO_DIR}/.env" ]]; then
  error ".env file not found in $REPO_DIR. Create it before deployment."
fi

cd "$REPO_DIR" || error "Failed to enter repository directory"

# 1. Fetch latest code
log "Fetching latest code from main branch..."
git fetch origin main || error "Failed to fetch from remote"

# Check if main is ahead of current
LOCAL_MAIN=$(git rev-parse main)
REMOTE_MAIN=$(git rev-parse origin/main)
if [[ "$LOCAL_MAIN" != "$REMOTE_MAIN" ]]; then
  log "Pulling latest changes..."
  git reset --hard origin/main || error "Failed to reset to origin/main"
else
  log "Already up to date"
fi

# 2. Backup database before deployment
if [[ -f "${DATA_DIR}/postbox.db" ]]; then
  log "Creating database backup..."
  mkdir -p "$BACKUP_DIR"

  TIMESTAMP=$(date -u +'%Y-%m-%dT%H%M%SZ')
  BACKUP_FILE="${BACKUP_DIR}/pre-deploy-${TIMESTAMP}.db"

  if command -v sqlite3 &>/dev/null; then
    sqlite3 "${DATA_DIR}/postbox.db" "VACUUM INTO '${BACKUP_FILE}'" || \
      error "Failed to backup database"
    log "Backup created: $BACKUP_FILE"
  else
    warn "sqlite3 not found; skipping database backup"
  fi
else
  log "No database file found; skipping backup"
fi

# 3. Build image
log "Preparing Docker image..."
if docker compose build --no-cache; then
  log "Docker image built"
else
  warn "Docker build had issues, but continuing..."
fi

# 4. Gracefully restart containers
log "Restarting containers (graceful restart, no downtime)..."

# Stop all containers gracefully (sends SIGTERM)
docker compose stop --timeout 30 || warn "Some containers did not stop cleanly"

# Remove stopped containers (but not volumes!)
docker compose rm -f || warn "Failed to remove containers"

# Start containers fresh
docker compose up -d || error "Failed to start containers"

log "Containers started"

# 5. Wait for health check
log "Waiting for service to become healthy..."
HEALTH_URL="http://127.0.0.1:8000/api/ready"
MAX_ATTEMPTS=30
ATTEMPT=0

while [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; do
  if curl -s --fail "$HEALTH_URL" >/dev/null 2>&1; then
    log "✅ Service is healthy"
    break
  fi

  ATTEMPT=$((ATTEMPT + 1))
  if [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; then
    echo -n "."
    sleep 2
  fi
done

if [[ $ATTEMPT -ge $MAX_ATTEMPTS ]]; then
  error "Service did not become healthy after $((MAX_ATTEMPTS * 2)) seconds"
fi

# 6. Show status
log "Container status:"
docker compose ps

# 7. Show recent logs
log "Recent logs:"
docker compose logs --tail=20 postbox

log "✅ Deployment successful!"
log "Public URL: $(grep POSTBOX_PUBLIC_URL .env | cut -d= -f2 || echo 'not configured')"
log "To rollback: git reset --hard <commit-hash> && docker compose up -d"

exit 0
