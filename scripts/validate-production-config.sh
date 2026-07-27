#!/usr/bin/env bash
# Validate that production configuration is safe before deployment.
# Meant to run in CI pipeline.

set -euo pipefail

echo "🔍 Validating production security configuration..."

ERRORS=0

# Check: DEV_LOGIN must be false/unset for production
if [[ "${POSTBOX_DEV_LOGIN:-false}" == "true" ]]; then
    echo "❌ ERROR: POSTBOX_DEV_LOGIN=true in production mode"
    ERRORS=$((ERRORS + 1))
fi

# Check: JWT_SECRET_KEY must be set and long enough
if [[ -z "${POSTBOX_JWT_SECRET_KEY:-}" ]]; then
    echo "❌ ERROR: POSTBOX_JWT_SECRET_KEY is not set"
    ERRORS=$((ERRORS + 1))
elif [[ ${#POSTBOX_JWT_SECRET_KEY} -lt 32 ]]; then
    echo "❌ ERROR: POSTBOX_JWT_SECRET_KEY is too short (min 32 chars, got ${#POSTBOX_JWT_SECRET_KEY})"
    ERRORS=$((ERRORS + 1))
else
    echo "✅ JWT_SECRET_KEY is set and long enough"
fi

# Check: BOT_TOKEN must be set if bot features are used
if [[ -z "${POSTBOX_BOT_TOKEN:-}" ]]; then
    echo "⚠️  WARNING: POSTBOX_BOT_TOKEN not set (Telegram login will show 'not configured')"
else
    echo "✅ BOT_TOKEN is set"
fi

# Check: PUBLIC_URL must be set
if [[ -z "${POSTBOX_PUBLIC_URL:-}" ]]; then
    echo "⚠️  WARNING: POSTBOX_PUBLIC_URL not set (may affect Telegram bot domain)"
else
    echo "✅ PUBLIC_URL is set to ${POSTBOX_PUBLIC_URL}"
fi

# Check: DATABASE_URL must not be :memory: or a dev path
if [[ "${POSTBOX_DATABASE_URL:-}" == *":memory:"* ]]; then
    echo "❌ ERROR: POSTBOX_DATABASE_URL is :memory: — data will be lost on restart"
    ERRORS=$((ERRORS + 1))
elif [[ "${POSTBOX_DATABASE_URL:-}" == *"./dev"* ]] || [[ "${POSTBOX_DATABASE_URL:-}" == *"/tmp/"* ]]; then
    echo "⚠️  WARNING: POSTBOX_DATABASE_URL looks like a dev path"
else
    echo "✅ DATABASE_URL looks like production path"
fi

# Final summary
echo ""
if [[ $ERRORS -eq 0 ]]; then
    echo "✅ All critical checks passed"
    exit 0
else
    echo "❌ $ERRORS critical error(s) found"
    exit 1
fi
