#!/bin/bash

# Screen2Deck E2E Test Runner
# Implements all test suites from TEST_PLAN_PLAYWRIGHT.md

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
BROWSER="chromium"
SUITE="all"
HEADED=false
DEBUG=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --browser)
      BROWSER="$2"
      shift 2
      ;;
    --suite)
      SUITE="$2"
      shift 2
      ;;
    --headed)
      HEADED=true
      shift
      ;;
    --debug)
      DEBUG=true
      shift
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --browser <name>  Browser to use (chromium, firefox, webkit, mobile, all)"
      echo "  --suite <name>    Test suite to run (s1-s14, all, smoke, full)"
      echo "  --headed          Run tests in headed mode"
      echo "  --debug           Run with debug output"
      echo "  --help            Show this help message"
      echo ""
      echo "Test Suites:"
      echo "  s1  - Happy path (upload → deck → export)"
      echo "  s2  - Parity (UI vs API vs Goldens)"
      echo "  s3  - Idempotence (re-upload, concurrency)"
      echo "  s4  - WebSocket (progression events)"
      echo "  s5  - Vision fallback"
      echo "  s6  - Offline Scryfall"
      echo "  s7  - Security upload"
      echo "  s8  - Error handling & UX"
      echo "  s9  - Accessibility (a11y)"
      echo "  s10 - Responsivity"
      echo "  s11 - Visual regression"
      echo "  s12 - Performance"
      echo "  s13 - Complex decks (DFC, Split, Adventure)"
      echo "  s14 - Anti-XSS security"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Check if services are running
check_services() {
  echo -e "${YELLOW}Checking services...${NC}"
  
  if ! curl -f http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${RED}Backend not running. Starting services...${NC}"
    docker compose --profile core up -d
    sleep 10
  fi
  
  if ! curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${RED}Webapp not running. Starting services...${NC}"
    docker compose --profile core up -d
    sleep 10
  fi
  
  echo -e "${GREEN}Services are ready${NC}"
}

# Install dependencies if needed
install_deps() {
  if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    npm install
  fi
  
  if [ ! -d "node_modules/@playwright/test/node_modules/.bin/playwright" ]; then
    echo -e "${YELLOW}Installing Playwright browsers...${NC}"
    npx playwright install --with-deps
  fi
}

# Build test command
build_command() {
  local cmd="npx playwright test"
  
  # Add suite selection
  case $SUITE in
    s1|s2|s3|s4|s5|s6|s7|s8|s9|s10|s11|s12|s13|s14)
      cmd="$cmd tests/web-e2e/suites/${SUITE}-*.spec.ts"
      ;;
    smoke)
      cmd="$cmd tests/web-e2e/suites/s1-happy-path.spec.ts tests/web-e2e/suites/s2-parity.spec.ts"
      ;;
    full|all)
      cmd="$cmd tests/web-e2e/suites/"
      ;;
  esac
  
  # Add browser selection
  if [ "$BROWSER" != "all" ]; then
    cmd="$cmd --project=$BROWSER"
  fi
  
  # Add headed mode
  if [ "$HEADED" = true ]; then
    cmd="$cmd --headed"
  fi
  
  # Add debug mode
  if [ "$DEBUG" = true ]; then
    cmd="$cmd --debug"
  fi
  
  echo "$cmd"
}

# Main execution
main() {
  echo -e "${GREEN}Screen2Deck E2E Test Runner${NC}"
  echo "================================"
  
  # Check environment
  install_deps
  check_services
  
  # Build and run command
  TEST_CMD=$(build_command)
  
  echo -e "${YELLOW}Running: $TEST_CMD${NC}"
  echo ""
  
  # Set environment variables
  export WEB_URL=http://localhost:3000
  export API_URL=http://localhost:8080
  export GOLDEN_DIR=./golden
  export DATASET_DIR=./validation_set
  export ENABLE_VISION_FALLBACK=false
  export SLO_P95_LATENCY_SEC=5
  export SLO_ACCURACY_MIN=0.92
  export SLO_CACHE_HIT_MIN=0.80
  
  # Run tests
  if $TEST_CMD; then
    echo ""
    echo -e "${GREEN}✅ Tests passed!${NC}"
    
    # Show report location
    echo ""
    echo "View detailed report: npx playwright show-report"
  else
    echo ""
    echo -e "${RED}❌ Tests failed${NC}"
    echo "View detailed report: npx playwright show-report"
    exit 1
  fi
}

# Run main function
main