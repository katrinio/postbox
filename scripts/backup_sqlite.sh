#!/bin/bash
#
# Backup Postbox SQLite database to a timestamped file.
#
# Usage:
#   ./scripts/backup_sqlite.sh
#   SOURCE_DB=/path/to/db BACKUP_DIR=/path/to/backups ./scripts/backup_sqlite.sh
#
# Environment variables:
#   SOURCE_DB         Path to SQLite database file (default: ./data/postbox.db)
#   BACKUP_DIR        Directory for backups (default: ./backups)
#   RETENTION_DAYS    Keep backups for N days (default: 14)
#

set -euo pipefail

# Configuration
SOURCE_DB="${SOURCE_DB:-./data/postbox.db}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

# Logging function
log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

error() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
  exit 1
}

log "Starting SQLite backup..."
log "Source: $SOURCE_DB"
log "Backup directory: $BACKUP_DIR"

# Validate source database exists
if [[ ! -f "$SOURCE_DB" ]]; then
  error "Database file not found: $SOURCE_DB"
fi

# Create backup directory
mkdir -p "$BACKUP_DIR" || error "Failed to create backup directory: $BACKUP_DIR"

# Generate timestamped backup filename (ISO 8601 format)
TIMESTAMP=$(date -u +'%Y-%m-%dT%H%M%SZ')
BACKUP_FILE="$BACKUP_DIR/postbox-${TIMESTAMP}.db"
BACKUP_TEMP="${BACKUP_FILE}.tmp"

# Create backup using sqlite3 VACUUM INTO (atomic, consistent)
# This creates a consistent snapshot without interrupting the application
if command -v sqlite3 &>/dev/null; then
  log "Creating backup using sqlite3 VACUUM INTO..."
  sqlite3 "$SOURCE_DB" "VACUUM INTO '${BACKUP_TEMP}'" || error "sqlite3 VACUUM INTO failed"
else
  error "sqlite3 command not found. Install sqlite3 package."
fi

# Atomically move temporary file to final location
mv "$BACKUP_TEMP" "$BACKUP_FILE" || error "Failed to finalize backup: $BACKUP_FILE"

log "Backup created: $BACKUP_FILE ($(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE") bytes)"

# Verify backup integrity
log "Verifying backup integrity..."
if ! sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -q "ok"; then
  error "Backup integrity check failed"
fi
log "Backup integrity verified"

# Clean up old backups (keep only recent ones)
log "Cleaning backups older than $RETENTION_DAYS days..."
CUTOFF_DATE=$(date -u -d "-$RETENTION_DAYS days" +'%Y-%m-%d' 2>/dev/null || date -u -v-${RETENTION_DAYS}d +'%Y-%m-%d')

DELETED_COUNT=0
while IFS= read -r old_file; do
  [[ -z "$old_file" ]] && continue
  rm -f "$old_file"
  log "Deleted old backup: $(basename "$old_file")"
  ((DELETED_COUNT++))
done < <(find "$BACKUP_DIR" -type f -name "postbox-*.db" -not -newermt "$CUTOFF_DATE" 2>/dev/null || true)

log "Cleanup complete: deleted $DELETED_COUNT old backups"

# Summary
BACKUP_COUNT=$(find "$BACKUP_DIR" -type f -name "postbox-*.db" 2>/dev/null | wc -l)
log "Backup complete. Total backups retained: $BACKUP_COUNT"
log "✅ Backup successful: $BACKUP_FILE"

exit 0
