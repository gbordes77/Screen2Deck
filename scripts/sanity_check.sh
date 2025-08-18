#!/bin/bash
# Sanity Checklist - Quick validation script
# Run this after setup to verify everything is wired correctly

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🔍 Screen2Deck Sanity Checklist"
echo "================================"

# 1. Port consistency check
echo -n "1. Port consistency (8080)... "
PORT_COUNT=$(grep -r "8080\|8000" backend docker-compose.yml Makefile webapp .github 2>/dev/null | grep -v node_modules | grep -v __pycache__ | grep -c "8000" || true)
if [ "$PORT_COUNT" -eq 0 ]; then
    echo -e "${GREEN}✅ All using 8080${NC}"
else
    echo -e "${YELLOW}⚠️  Found $PORT_COUNT references to port 8000 (should be 8080)${NC}"
fi

# 2. Health endpoint
echo -n "2. Health endpoint... "
if curl -fsS http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Responding${NC}"
else
    echo -e "${RED}❌ Not responding${NC}"
fi

# 3. Prometheus metrics
echo -n "3. Prometheus metrics... "
METRICS=$(curl -s http://localhost:8080/metrics 2>/dev/null | grep -c "s2d_" || echo "0")
if [ "$METRICS" -gt 0 ]; then
    echo -e "${GREEN}✅ Exposed ($METRICS metrics)${NC}"
else
    echo -e "${RED}❌ No custom metrics found${NC}"
fi

# 4. Export endpoints (public)
echo -n "4. Export endpoints (public)... "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8080/api/export/mtga \
    -H 'Content-Type: application/json' \
    -d '{"main":[{"qty":4,"name":"Island"}],"side":[]}' 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Public access OK${NC}"
elif [ "$HTTP_CODE" = "401" ]; then
    echo -e "${RED}❌ Requires auth (should be public)${NC}"
else
    echo -e "${RED}❌ Error (HTTP $HTTP_CODE)${NC}"
fi

# 5. Redis connection
echo -n "5. Redis connection... "
if docker compose exec redis redis-cli ping 2>/dev/null | grep -q PONG; then
    echo -e "${GREEN}✅ Connected${NC}"
else
    echo -e "${YELLOW}⚠️  Not connected or not running${NC}"
fi

# 6. Feature flags
echo -n "6. Feature flags check... "
VISION_FLAG=$(grep "VISION_OCR_FALLBACK" .env.benchmark 2>/dev/null | grep -c "off" || echo "0")
SCRYFALL_FLAG=$(grep "SCRYFALL_ONLINE" .env.benchmark 2>/dev/null | grep -c "off" || echo "0")
if [ "$VISION_FLAG" -eq 1 ] && [ "$SCRYFALL_FLAG" -eq 1 ]; then
    echo -e "${GREEN}✅ Safe defaults (Vision OFF, Scryfall OFFLINE)${NC}"
else
    echo -e "${YELLOW}⚠️  Check .env.benchmark flags${NC}"
fi

# 7. Determinism settings
echo -n "7. Determinism settings... "
if [ -f backend/app/core/determinism.py ]; then
    echo -e "${GREEN}✅ Module exists${NC}"
else
    echo -e "${RED}❌ determinism.py not found${NC}"
fi

# 8. Idempotency module
echo -n "8. Idempotency module... "
if [ -f backend/app/core/idempotency.py ]; then
    echo -e "${GREEN}✅ Module exists${NC}"
else
    echo -e "${RED}❌ idempotency.py not found${NC}"
fi

# 9. Benchmark script
echo -n "9. Benchmark script... "
if [ -x tools/benchmark_independent.py ]; then
    echo -e "${GREEN}✅ Executable${NC}"
else
    echo -e "${RED}❌ Not found or not executable${NC}"
fi

# 10. Dataset for testing
echo -n "10. Test dataset... "
IMAGE_COUNT=$(ls validation_set/*.{png,jpg,jpeg} 2>/dev/null | wc -l || echo "0")
if [ "$IMAGE_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✅ Found $IMAGE_COUNT images${NC}"
else
    echo -e "${RED}❌ No test images found${NC}"
fi

echo ""
echo "================================"
echo "Summary:"
echo ""

# Quick benchmark test (if all green)
if [ "$METRICS" -gt 0 ] && [ "$HTTP_CODE" = "200" ] && [ "$IMAGE_COUNT" -gt 0 ]; then
    echo "✅ System ready for benchmarking!"
    echo ""
    echo "Run: make bench-truth"
else
    echo "⚠️  Fix issues above before running benchmark"
fi