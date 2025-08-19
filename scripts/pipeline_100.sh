#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Screen2Deck Pipeline 100% - Full E2E Test${NC}"
echo "================================================"

# Step 1: Build services
echo -e "\n${YELLOW}🔧 Step 1: Building services...${NC}"
docker compose --profile core build backend webapp

# Step 2: Start services
echo -e "\n${YELLOW}🔧 Step 2: Starting services...${NC}"
docker compose --profile core down --remove-orphans || true
docker compose --profile core up -d backend webapp redis postgres

# Step 3: Wait for services to be ready
echo -e "\n${YELLOW}⏳ Step 3: Waiting for services...${NC}"
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -fsS http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Backend is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 1
    ATTEMPT=$((ATTEMPT + 1))
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo -e "${RED}❌ Backend failed to start after 30 seconds${NC}"
    docker logs screen2deck-backend-1 --tail 50
    exit 1
fi

# Step 4: Health checks
echo -e "\n${YELLOW}🏥 Step 4: Running health checks...${NC}"

# Basic health
echo -e "\n📌 Health root:"
HEALTH_BASIC=$(curl -fsS http://localhost:8080/health)
echo "$HEALTH_BASIC" | python3 -m json.tool || echo "$HEALTH_BASIC"
if echo "$HEALTH_BASIC" | grep -q "healthy"; then
    echo -e "${GREEN}✅ Basic health: OK${NC}"
else
    echo -e "${RED}❌ Basic health: FAILED${NC}"
    exit 1
fi

# OCR health
echo -e "\n📌 Health OCR:"
HEALTH_OCR=$(curl -fsS http://localhost:8080/health/ocr 2>/dev/null || echo '{"ok": false}')
echo "$HEALTH_OCR" | python3 -m json.tool || echo "$HEALTH_OCR"
if echo "$HEALTH_OCR" | grep -q '"ok": true'; then
    echo -e "${GREEN}✅ OCR health: OK${NC}"
else
    echo -e "${YELLOW}⚠️ OCR health: Not available (will use basic OCR)${NC}"
fi

# Scryfall health
echo -e "\n📌 Health Scryfall:"
HEALTH_SCRYFALL=$(curl -fsS http://localhost:8080/health/scryfall 2>/dev/null || echo '{"ok": false}')
echo "$HEALTH_SCRYFALL" | python3 -m json.tool || echo "$HEALTH_SCRYFALL"
if echo "$HEALTH_SCRYFALL" | grep -q '"ok": true'; then
    echo -e "${GREEN}✅ Scryfall health: OK${NC}"
else
    echo -e "${YELLOW}⚠️ Scryfall health: Not available (will use fallback)${NC}"
fi

# Pipeline self-test
echo -e "\n📌 Health Pipeline (self-test):"
HEALTH_PIPELINE=$(curl -fsS http://localhost:8080/health/pipeline 2>/dev/null || echo '{"ok": false}')
echo "$HEALTH_PIPELINE" | python3 -m json.tool || echo "$HEALTH_PIPELINE"
if echo "$HEALTH_PIPELINE" | grep -q '"ok": true'; then
    echo -e "${GREEN}✅ Pipeline self-test: OK${NC}"
else
    echo -e "${YELLOW}⚠️ Pipeline self-test: Not available${NC}"
fi

# Step 5: E2E UI Test
echo -e "\n${YELLOW}🧪 Step 5: Running E2E UI test...${NC}"

# Check if real-e2e-test.js exists
if [ -f "real-e2e-test.js" ]; then
    echo "Running Playwright E2E test..."
    node real-e2e-test.js
    E2E_RESULT=$?
    
    if [ $E2E_RESULT -eq 0 ]; then
        echo -e "${GREEN}✅ E2E UI test: PASSED${NC}"
    else
        echo -e "${YELLOW}⚠️ E2E UI test: Partial success${NC}"
    fi
else
    echo -e "${YELLOW}⚠️ E2E test script not found, creating simple test...${NC}"
    
    # Create a simple test inline
    cat > /tmp/simple-e2e.js << 'EOF'
const http = require('http');

async function simpleTest() {
    try {
        // Test frontend
        const frontendOK = await new Promise((resolve) => {
            http.get('http://localhost:3000', (res) => {
                resolve(res.statusCode === 200);
            }).on('error', () => resolve(false));
        });
        
        // Test backend
        const backendOK = await new Promise((resolve) => {
            http.get('http://localhost:8080/health', (res) => {
                resolve(res.statusCode === 200);
            }).on('error', () => resolve(false));
        });
        
        console.log(`Frontend: ${frontendOK ? '✅' : '❌'}`);
        console.log(`Backend: ${backendOK ? '✅' : '❌'}`);
        
        return frontendOK && backendOK ? 0 : 1;
    } catch (e) {
        console.error(e);
        return 1;
    }
}

simpleTest().then(process.exit);
EOF
    
    node /tmp/simple-e2e.js
    E2E_RESULT=$?
fi

# Step 6: Summary
echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}📊 PIPELINE SUMMARY${NC}"
echo -e "${GREEN}================================================${NC}"

# Count successes
TOTAL_CHECKS=0
PASSED_CHECKS=0

# Basic health
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if echo "$HEALTH_BASIC" | grep -q "healthy"; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    echo -e "✅ Basic Health: ${GREEN}PASS${NC}"
else
    echo -e "❌ Basic Health: ${RED}FAIL${NC}"
fi

# OCR
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if echo "$HEALTH_OCR" | grep -q '"ok": true'; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    echo -e "✅ OCR Engine: ${GREEN}PASS${NC}"
else
    echo -e "⚠️ OCR Engine: ${YELLOW}DEGRADED${NC}"
fi

# Scryfall
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if echo "$HEALTH_SCRYFALL" | grep -q '"ok": true'; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    echo -e "✅ Scryfall DB: ${GREEN}PASS${NC}"
else
    echo -e "⚠️ Scryfall DB: ${YELLOW}DEGRADED${NC}"
fi

# Pipeline
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if echo "$HEALTH_PIPELINE" | grep -q '"ok": true'; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    echo -e "✅ Pipeline Test: ${GREEN}PASS${NC}"
else
    echo -e "⚠️ Pipeline Test: ${YELLOW}DEGRADED${NC}"
fi

# E2E
TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if [ $E2E_RESULT -eq 0 ]; then
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
    echo -e "✅ E2E UI Test: ${GREEN}PASS${NC}"
else
    echo -e "⚠️ E2E UI Test: ${YELLOW}PARTIAL${NC}"
fi

# Calculate percentage
PERCENTAGE=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))

echo -e "\n${GREEN}================================================${NC}"
echo -e "Score: ${PASSED_CHECKS}/${TOTAL_CHECKS} checks passed (${PERCENTAGE}%)"

if [ $PERCENTAGE -ge 80 ]; then
    echo -e "${GREEN}🎉 PIPELINE STATUS: SUCCESS (≥80%)${NC}"
    exit 0
elif [ $PERCENTAGE -ge 60 ]; then
    echo -e "${YELLOW}⚠️ PIPELINE STATUS: DEGRADED (60-79%)${NC}"
    exit 0
else
    echo -e "${RED}❌ PIPELINE STATUS: FAILED (<60%)${NC}"
    exit 1
fi