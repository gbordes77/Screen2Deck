#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🎭 Screen2Deck E2E Test Runner"
echo "================================"

# Check if Docker is running first
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running!${NC}"
    echo "Run: ./check-docker.sh first"
    exit 1
fi

# Check if Playwright is installed
if ! npm list @playwright/test > /dev/null 2>&1; then
    echo -e "${YELLOW}📦 Installing Playwright...${NC}"
    npm install -D @playwright/test axe-playwright
    npx playwright install --with-deps
fi

# Set environment variables
export WEB_URL=${WEB_URL:-"http://localhost:3000"}
export API_URL=${API_URL:-"http://localhost:8080"}
export GOLDEN_DIR=${GOLDEN_DIR:-"./golden"}
export DATASET_DIR=${DATASET_DIR:-"./validation_set"}

# Parse command line arguments
TEST_TYPE=${1:-"all"}

case $TEST_TYPE in
    "setup")
        echo -e "${GREEN}🔧 Running setup validation tests...${NC}"
        npx playwright test tests/e2e/setup.spec.ts --reporter=list
        ;;
    "happy")
        echo -e "${GREEN}😊 Running happy path tests...${NC}"
        npx playwright test tests/e2e/happy-path.spec.ts --reporter=list
        ;;
    "parity")
        echo -e "${GREEN}🔄 Running API parity tests...${NC}"
        npx playwright test tests/e2e/api-parity.spec.ts --reporter=list
        ;;
    "idempotency")
        echo -e "${GREEN}♻️ Running idempotency tests...${NC}"
        npx playwright test tests/e2e/idempotency.spec.ts --reporter=list
        ;;
    "accessibility")
        echo -e "${GREEN}♿ Running accessibility tests...${NC}"
        npx playwright test tests/e2e/accessibility.spec.ts --reporter=list
        ;;
    "security")
        echo -e "${GREEN}🔒 Running security tests...${NC}"
        npx playwright test tests/e2e/security.spec.ts --reporter=list
        ;;
    "performance")
        echo -e "${GREEN}⚡ Running performance tests...${NC}"
        npx playwright test tests/e2e/performance.spec.ts --reporter=list
        ;;
    "all")
        echo -e "${GREEN}🚀 Running all E2E tests...${NC}"
        npx playwright test --reporter=list,html
        ;;
    "chrome")
        echo -e "${GREEN}🌐 Running tests in Chrome only...${NC}"
        npx playwright test --project=chromium --reporter=list
        ;;
    "firefox")
        echo -e "${GREEN}🦊 Running tests in Firefox only...${NC}"
        npx playwright test --project=firefox --reporter=list
        ;;
    "safari")
        echo -e "${GREEN}🧭 Running tests in Safari only...${NC}"
        npx playwright test --project=webkit --reporter=list
        ;;
    "mobile")
        echo -e "${GREEN}📱 Running mobile tests...${NC}"
        npx playwright test --project=mobile --reporter=list
        ;;
    "report")
        echo -e "${GREEN}📊 Opening test report...${NC}"
        npx playwright show-report
        ;;
    "help")
        echo "Usage: ./run-e2e-tests.sh [command]"
        echo ""
        echo "Commands:"
        echo "  setup         - Run setup validation tests"
        echo "  happy         - Run happy path tests"
        echo "  parity        - Run API parity tests"
        echo "  idempotency   - Run idempotency tests"
        echo "  accessibility - Run accessibility tests"
        echo "  security      - Run security tests"
        echo "  performance   - Run performance tests"
        echo "  all           - Run all tests (default)"
        echo "  chrome        - Run tests in Chrome only"
        echo "  firefox       - Run tests in Firefox only"
        echo "  safari        - Run tests in Safari only"
        echo "  mobile        - Run mobile tests"
        echo "  report        - Open HTML test report"
        echo "  help          - Show this help message"
        ;;
    *)
        echo -e "${RED}Unknown command: $TEST_TYPE${NC}"
        echo "Run: ./run-e2e-tests.sh help"
        exit 1
        ;;
esac

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Tests completed successfully!${NC}"
    
    # Offer to open report for full test runs
    if [[ "$TEST_TYPE" == "all" ]]; then
        echo ""
        echo "View the HTML report with: ./run-e2e-tests.sh report"
    fi
else
    echo -e "${RED}❌ Tests failed!${NC}"
    echo "Check the output above for details"
    
    # Offer to open report for debugging
    echo ""
    echo "View detailed report with: ./run-e2e-tests.sh report"
    exit 1
fi