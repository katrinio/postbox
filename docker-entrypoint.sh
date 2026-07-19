#!/bin/bash
set -e

echo "Starting Postbox application..."

# Start API in background
echo "Starting API server..."
cd /app
poetry run postbox-api &
API_PID=$!

# Start Web in background
echo "Starting Web server..."
cd /app/web
npm start &
WEB_PID=$!

# Wait for both processes
wait $API_PID $WEB_PID
