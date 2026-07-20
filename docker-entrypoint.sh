#!/bin/sh
set -eu

API_PID=""
WEB_PID=""
SHUTTING_DOWN=0

echo "Starting Postbox application..."

shutdown() {
  signal="${1:-SIGTERM}"

  if [ "$SHUTTING_DOWN" -eq 1 ]; then
    return
  fi

  SHUTTING_DOWN=1
  echo "Received $signal, shutting down..."

  if [ -n "$API_PID" ]; then
    kill -TERM "$API_PID" 2>/dev/null || true
  fi

  if [ -n "$WEB_PID" ]; then
    kill -TERM "$WEB_PID" 2>/dev/null || true
  fi

  waited=0

  while [ "$waited" -lt 30 ]; do
    api_alive=0
    web_alive=0

    if [ -n "$API_PID" ] && kill -0 "$API_PID" 2>/dev/null; then
      api_alive=1
    fi

    if [ -n "$WEB_PID" ] && kill -0 "$WEB_PID" 2>/dev/null; then
      web_alive=1
    fi

    if [ "$api_alive" -eq 0 ] && [ "$web_alive" -eq 0 ]; then
      wait "$API_PID" 2>/dev/null || true
      wait "$WEB_PID" 2>/dev/null || true

      echo "All processes shut down gracefully"
      return
    fi

    sleep 1
    waited=$((waited + 1))
  done

  echo "Forcing shutdown of remaining processes..."

  if [ -n "$API_PID" ]; then
    kill -KILL "$API_PID" 2>/dev/null || true
  fi

  if [ -n "$WEB_PID" ]; then
    kill -KILL "$WEB_PID" 2>/dev/null || true
  fi

  wait "$API_PID" 2>/dev/null || true
  wait "$WEB_PID" 2>/dev/null || true
}

handle_signal() {
  shutdown "$1"
  exit 0
}

trap 'handle_signal SIGTERM' TERM
trap 'handle_signal SIGINT' INT

# Start API in background
echo "Starting API server on 127.0.0.1:8000..."
cd /app
postbox-api &
API_PID=$!

# Start Web in background
echo "Starting Web server on 127.0.0.1:3000..."
cd /app/web
npm start &
WEB_PID=$!

echo "Postbox processes started (API: $API_PID, Web: $WEB_PID)"

# Wait for both services to become ready (max 30 seconds).
echo "Waiting for services to be ready..."
waited=0
while [ "$waited" -lt 30 ]; do
  # Check if both processes are still alive
  if ! kill -0 "$API_PID" 2>/dev/null || ! kill -0 "$WEB_PID" 2>/dev/null; then
    echo "ERROR: A process died during startup"
    shutdown "Startup failure"
    exit 1
  fi

  # Test both endpoints
  api_ready=0
  web_ready=0

  curl --fail --silent http://127.0.0.1:8000/api/ready >/dev/null 2>&1 && api_ready=1
  curl --fail --silent http://127.0.0.1:3000/ >/dev/null 2>&1 && web_ready=1

  if [ "$api_ready" -eq 1 ] && [ "$web_ready" -eq 1 ]; then
    echo "✓ All services are ready"
    break
  fi

  sleep 1
  waited=$((waited + 1))
done

if [ "$waited" -ge 30 ]; then
  echo "WARNING: Services did not become ready within 30s, continuing anyway"
fi

# Monitor both processes and stop the container if either one exits.
while true; do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    if wait "$API_PID"; then
      EXIT_CODE=0
    else
      EXIT_CODE=$?
    fi

    echo "API process exited with code $EXIT_CODE"
    shutdown "API exit"
    exit "$EXIT_CODE"
  fi

  if ! kill -0 "$WEB_PID" 2>/dev/null; then
    if wait "$WEB_PID"; then
      EXIT_CODE=0
    else
      EXIT_CODE=$?
    fi

    echo "Web process exited with code $EXIT_CODE"
    shutdown "Web exit"
    exit "$EXIT_CODE"
  fi

  sleep 1
done
