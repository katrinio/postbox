#!/bin/bash
# Start Postbox application (both API and web frontend)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if poetry is installed
if ! command -v poetry &> /dev/null; then
    echo -e "${RED}Error: poetry is not installed${NC}"
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: npm is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}Starting Postbox application...${NC}\n"

# Start API in background
echo -e "${YELLOW}Starting API on http://localhost:8000${NC}"
poetry run postbox-api &
API_PID=$!

# Give API time to start
sleep 2

# Start web frontend in background
echo -e "${YELLOW}Starting Web on http://localhost:3000${NC}"
cd web
npm run dev &
WEB_PID=$!

echo -e "\n${GREEN}✅ Postbox is running!${NC}\n"
echo -e "📖 Web: ${GREEN}http://localhost:3000${NC}"
echo -e "🔌 API: ${GREEN}http://localhost:8000${NC}\n"

echo -e "${YELLOW}Press Ctrl+C to stop both services${NC}\n"

# Handle cleanup
trap "kill $API_PID $WEB_PID 2>/dev/null; exit 0" SIGINT SIGTERM

# Wait for processes
wait
