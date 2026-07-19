#!/bin/bash
#
# Verify SQLite backup is restorable.
#
# Usage:
#   ./scripts/verify_backup.sh backups/postbox-2026-07-19T050000Z.db
#   ./scripts/verify_backup.sh  # uses latest backup
#

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
BACKUP_FILE="${1:-}"

# Logging
log() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*"
}

error() {
  echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
  exit 1
}

# If no file specified, use latest
if [[ -z "$BACKUP_FILE" ]]; then
  BACKUP_FILE=$(ls -t "$BACKUP_DIR"/postbox-*.db 2>/dev/null | head -1 || true)
  if [[ -z "$BACKUP_FILE" ]]; then
    error "No backup found in $BACKUP_DIR"
  fi
  log "Using latest backup: $(basename "$BACKUP_FILE")"
fi

# Validate backup exists
if [[ ! -f "$BACKUP_FILE" ]]; then
  error "Backup file not found: $BACKUP_FILE"
fi

log "Verifying backup: $BACKUP_FILE"

# Create temporary test directory
TEST_DIR=$(mktemp -d) || error "Failed to create temp directory"
trap "rm -rf '$TEST_DIR'" EXIT

TEST_DB="$TEST_DIR/test.db"

log "Restoring backup to temporary database..."
cp "$BACKUP_FILE" "$TEST_DB" || error "Failed to copy backup"

# Check integrity
log "Running PRAGMA integrity_check..."
if ! sqlite3 "$TEST_DB" "PRAGMA integrity_check;" | grep -q "ok"; then
  error "Backup integrity check failed"
fi
log "✅ Integrity check passed"

# Check schema exists
log "Verifying schema..."
TABLE_COUNT=$(sqlite3 "$TEST_DB" "SELECT COUNT(*) FROM sqlite_master WHERE type='table';" 2>/dev/null || echo "0")
if [[ "$TABLE_COUNT" -lt 1 ]]; then
  error "No tables found in backup (corrupted or empty)"
fi
log "✅ Found $TABLE_COUNT table(s)"

# Check critical tables
log "Verifying critical tables..."
for table in users mail_items correspondents; do
  if sqlite3 "$TEST_DB" ".tables" | grep -q "$table"; then
    COUNT=$(sqlite3 "$TEST_DB" "SELECT COUNT(*) FROM $table;" 2>/dev/null || echo "0")
    log "  ✅ Table '$table' has $COUNT row(s)"
  else
    log "  ⚠️  Table '$table' not found (may be normal for new backups)"
  fi
done

log "✅ Backup verification successful: $BACKUP_FILE"
log "   Database is safe to restore"

exit 0
