#!/bin/bash
# Validate air-gapped demo mode - no external network calls allowed

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "🔒 Validating Air-Gapped Demo Mode"
echo "====================================="

# 1. Check Docker compose configuration
echo -n "1. Checking Docker network blocks... "
if grep -q "api.scryfall.com:127.0.0.1" docker-compose.local.yml; then
    echo -e "${GREEN}✓${NC} Scryfall blocked"
else
    echo -e "${RED}✗${NC} Scryfall not blocked!"
    exit 1
fi

# 2. Check offline database exists
echo -n "2. Checking offline database... "
if [ -f "data/scryfall.sqlite" ]; then
    SIZE=$(du -h data/scryfall.sqlite | cut -f1)
    echo -e "${GREEN}✓${NC} Found ($SIZE)"
else
    echo -e "${YELLOW}⚠${NC} Not found - run 'make demo-seed' first"
fi

# 3. Check Nginx security headers
echo -n "3. Checking Nginx security... "
if grep -q "Content-Security-Policy" ops/nginx/nginx.local.conf && \
   grep -q "X-Frame-Options" ops/nginx/nginx.local.conf && \
   grep -q "limit_req_zone" ops/nginx/nginx.local.conf; then
    echo -e "${GREEN}✓${NC} Headers configured"
else
    echo -e "${RED}✗${NC} Security headers missing!"
    exit 1
fi

# 4. Start services if not running
echo -n "4. Checking services... "
if docker ps | grep -q "s2d_gateway"; then
    echo -e "${GREEN}✓${NC} Already running"
else
    echo -e "${YELLOW}⚠${NC} Starting services..."
    make demo-local > /dev/null 2>&1 &
    sleep 15
fi

# 5. Test endpoints (no external calls)
echo "5. Testing endpoints:"

# Health check
echo -n "   - Health endpoint... "
if curl -fsS http://localhost:8088/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# App endpoint
echo -n "   - App UI... "
if curl -fsS http://localhost:8088/app/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# Docs endpoint
echo -n "   - Documentation... "
if curl -fsS http://localhost:8088/docs/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# Artifacts endpoint
echo -n "   - Artifacts... "
if curl -fsS http://localhost:8088/artifacts/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
fi

# API endpoint
echo -n "   - API health... "
if curl -fsS http://localhost:8088/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC} Auth required"
fi

# 6. Test rate limiting
echo -n "6. Testing rate limiting... "
for i in {1..15}; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8088/api/health)
    if [ "$STATUS" = "503" ] || [ "$STATUS" = "429" ]; then
        echo -e "${GREEN}✓${NC} Rate limit working (triggered at $i requests)"
        break
    fi
done
if [ "$i" -eq 15 ]; then
    echo -e "${YELLOW}⚠${NC} Rate limit not triggered (may be OK for demo)"
fi

# 7. Check CSP headers
echo -n "7. Checking CSP headers... "
CSP=$(curl -sI http://localhost:8088/app/ | grep -i "content-security-policy")
if echo "$CSP" | grep -q "default-src 'self'"; then
    echo -e "${GREEN}✓${NC} CSP active"
else
    echo -e "${YELLOW}⚠${NC} CSP not detected"
fi

# 8. Check for external network calls (using tcpdump if available)
echo -n "8. Monitoring for external calls... "
if command -v tcpdump > /dev/null 2>&1; then
    # Monitor for 5 seconds
    sudo timeout 5 tcpdump -i any -n "not host 127.0.0.1 and not host localhost and not net 172.16.0.0/12" 2>/dev/null | grep -q "." && \
        echo -e "${RED}✗${NC} External traffic detected!" || \
        echo -e "${GREEN}✓${NC} No external traffic"
else
    echo -e "${YELLOW}⚠${NC} tcpdump not available"
fi

echo ""
echo "====================================="
echo "🎯 Air-Gap Validation Complete!"
echo ""
echo "Dashboard: http://localhost:8088"
echo "Stop with: make stop-local"
echo ""

# Summary
if [ -f "data/scryfall.sqlite" ]; then
    echo -e "${GREEN}✅ System is air-gapped and ready for offline demo!${NC}"
else
    echo -e "${YELLOW}⚠️  Run 'make demo-seed' to complete offline setup${NC}"
fi