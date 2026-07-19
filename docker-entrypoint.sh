#!/bin/sh
set -euo pipefail

echo "Starting Postbox application..."

# Start API in background
echo "Starting API server on 127.0.0.1:8000..."
cd /app
poetry run postbox-api &
API_PID=$!

# Start Web in background
echo "Starting Web server on 127.0.0.1:3000..."
cd /app/web
npm start &
WEB_PID=$!

echo "Postbox processes started (API: $API_PID, Web: $WEB_PID)"

# Handle SIGTERM and SIGINT to gracefully shut down
trap_handler() {
  local signal=$1
  echo "Received $signal, shutting down..."

  # Send SIGTERM to both processes
  kill -TERM $API_PID $WEB_PID 2>/dev/null || true

  # Wait for graceful shutdown (max 30 seconds)
  local waited=0
  while [ $waited -lt 30 ]; do
    if ! kill -0 $API_PID 2>/dev/null && ! kill -0 $WEB_PID 2>/dev/null; then
      echo "All processes shut down gracefully"
      exit 0
    fi
    sleep 1
    waited=$((waited + 1))
  done

  # Force kill if still running
  echo "Forcing shutdown of remaining processes..."
  kill -9 $API_PID $WEB_PID 2>/dev/null || true
  exit 0
}

trap "trap_handler SIGTERM" SIGTERM
trap "trap_handler SIGINT" SIGINT

# Wait for both processes; if either dies, exit
wait $API_PID $WEB_PID
EXIT_CODE=$?

echo "Process exited with code $EXIT_CODE"
exit $EXIT_CODE
