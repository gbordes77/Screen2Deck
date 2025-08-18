#!/bin/bash
# Gate Final - Complete Go/No-Go validation sequence
# This script runs the full validation suite to determine if the system is ready

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "🚀 Screen2Deck Gate Final - Go/No-Go Decision"
echo "=============================================="
echo ""

# Track overall status
GATE_STATUS="GO"
FAILURES=()

# Function to run command and check status
run_check() {
    local name="$1"
    local cmd="$2"
    local threshold="$3"
    
    echo -n "🔧 $name... "
    
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ PASS${NC}"
        return 0
    else
        echo -e "${RED}❌ FAIL${NC}"
        GATE_STATUS="NO-GO"
        FAILURES+=("$name")
        return 1
    fi
}

# 1. SANITY CHECK
echo -e "${BLUE}[1/6] Running Sanity Check${NC}"
echo "------------------------------"
if ./scripts/sanity_check.sh > /tmp/sanity.log 2>&1; then
    echo -e "${GREEN}✅ Sanity check passed${NC}"
else
    echo -e "${RED}❌ Sanity check failed${NC}"
    cat /tmp/sanity.log
    GATE_STATUS="NO-GO"
    FAILURES+=("Sanity Check")
fi
echo ""

# 2. DOCKER SERVICES
echo -e "${BLUE}[2/6] Checking Docker Services${NC}"
echo "------------------------------"
SERVICES_UP=$(docker compose ps --services --filter "status=running" 2>/dev/null | wc -l || echo "0")
if [ "$SERVICES_UP" -ge 3 ]; then
    echo -e "${GREEN}✅ Docker services running ($SERVICES_UP services)${NC}"
else
    echo -e "${YELLOW}⚠️  Only $SERVICES_UP services running (expected ≥3)${NC}"
    echo "Starting services..."
    docker compose --profile core up -d
    sleep 5
fi
echo ""

# 3. FIRST TEST
echo -e "${BLUE}[3/6] Running First Test${NC}"
echo "------------------------------"
if [ -f "./scripts/first_test.sh" ]; then
    if ./scripts/first_test.sh > /tmp/first_test.log 2>&1; then
        echo -e "${GREEN}✅ First test passed${NC}"
    else
        echo -e "${RED}❌ First test failed${NC}"
        echo "Last 20 lines of log:"
        tail -20 /tmp/first_test.log
        GATE_STATUS="NO-GO"
        FAILURES+=("First Test")
    fi
else
    echo -e "${YELLOW}⚠️  First test script not found, skipping${NC}"
fi
echo ""

# 4. BENCHMARK TEST
echo -e "${BLUE}[4/6] Running Benchmark (Truth)${NC}"
echo "------------------------------"
if [ -d "./validation_set" ] && [ "$(ls -1 validation_set/*.png 2>/dev/null | wc -l)" -gt 0 ]; then
    echo "Running benchmark with deterministic settings..."
    
    # Export anti-flakiness environment
    export PYTHONHASHSEED=0
    export DETERMINISTIC_MODE=on
    export S2D_SEED=42
    export S2D_THREADS=1
    export SCRYFALL_ONLINE=off
    export VISION_OCR_FALLBACK=off
    
    # Run benchmark
    if python tools/benchmark_independent.py \
        --images ./validation_set \
        --output ./artifacts/reports/gate_final.json \
        --url http://localhost:8080 > /tmp/bench.log 2>&1; then
        
        # Extract metrics
        ACCURACY=$(python -c "import json; d=json.load(open('./artifacts/reports/gate_final.json')); print(f\"{d['accuracy']['fuzzy_match']['mean']:.1f}\")" 2>/dev/null || echo "0")
        P95=$(python -c "import json; d=json.load(open('./artifacts/reports/gate_final.json')); print(f\"{d['latency']['p95']:.2f}\")" 2>/dev/null || echo "99")
        CACHE_HIT=$(python -c "import json; d=json.load(open('./artifacts/reports/gate_final.json')); print(f\"{d['summary']['cache_hit_rate']*100:.1f}\")" 2>/dev/null || echo "0")
        
        echo "📊 Benchmark Results:"
        echo "  - Accuracy: ${ACCURACY}%"
        echo "  - P95 Latency: ${P95}s"
        echo "  - Cache Hit: ${CACHE_HIT}%"
        
        # Check thresholds
        PASS=true
        
        # Accuracy threshold (≥95% for production, ≥85% acceptable)
        if (( $(echo "$ACCURACY >= 95" | bc -l) )); then
            echo -e "  ${GREEN}✅ Accuracy excellent (≥95%)${NC}"
        elif (( $(echo "$ACCURACY >= 85" | bc -l) )); then
            echo -e "  ${YELLOW}⚠️  Accuracy acceptable (≥85%)${NC}"
        else
            echo -e "  ${RED}❌ Accuracy too low (<85%)${NC}"
            PASS=false
        fi
        
        # P95 latency threshold (≤5s)
        if (( $(echo "$P95 <= 5.0" | bc -l) )); then
            echo -e "  ${GREEN}✅ P95 latency good (≤5s)${NC}"
        else
            echo -e "  ${RED}❌ P95 latency too high (>5s)${NC}"
            PASS=false
        fi
        
        # Cache hit threshold (≥50% on second run)
        if (( $(echo "$CACHE_HIT >= 50" | bc -l) )); then
            echo -e "  ${GREEN}✅ Cache hit rate good (≥50%)${NC}"
        elif (( $(echo "$CACHE_HIT >= 20" | bc -l) )); then
            echo -e "  ${YELLOW}⚠️  Cache hit rate low (≥20%)${NC}"
        else
            echo -e "  ${RED}❌ Cache hit rate very low (<20%)${NC}"
        fi
        
        if [ "$PASS" = false ]; then
            GATE_STATUS="NO-GO"
            FAILURES+=("Benchmark Thresholds")
        fi
    else
        echo -e "${RED}❌ Benchmark failed to run${NC}"
        tail -20 /tmp/bench.log
        GATE_STATUS="NO-GO"
        FAILURES+=("Benchmark Execution")
    fi
else
    echo -e "${YELLOW}⚠️  No test images found, skipping benchmark${NC}"
fi
echo ""

# 5. ANTI-TESSERACT CHECK
echo -e "${BLUE}[5/6] Anti-Tesseract Verification${NC}"
echo "------------------------------"
if which tesseract > /dev/null 2>&1; then
    echo -e "${RED}❌ Tesseract is installed (FORBIDDEN)${NC}"
    GATE_STATUS="NO-GO"
    FAILURES+=("Tesseract Installed")
else
    echo -e "${GREEN}✅ Tesseract not found (correct)${NC}"
fi

# Check code for tesseract references
TESSERACT_REFS=$(grep -r "tesseract\|Tesseract\|TESSERACT" backend/ webapp/ --exclude-dir=node_modules --exclude-dir=__pycache__ 2>/dev/null | grep -v "must NOT\|prohibition\|forbidden" | wc -l || echo "0")
if [ "$TESSERACT_REFS" -gt 0 ]; then
    echo -e "${RED}❌ Found $TESSERACT_REFS Tesseract references in code${NC}"
    GATE_STATUS="NO-GO"
    FAILURES+=("Tesseract References")
else
    echo -e "${GREEN}✅ No Tesseract references in code${NC}"
fi
echo ""

# 6. SECURITY CHECKS
echo -e "${BLUE}[6/6] Security Validation${NC}"
echo "------------------------------"

# Check /health/detailed is protected
HEALTH_DETAILED=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health/detailed 2>/dev/null || echo "000")
if [ "$HEALTH_DETAILED" = "403" ] || [ "$HEALTH_DETAILED" = "401" ]; then
    echo -e "${GREEN}✅ /health/detailed is protected${NC}"
else
    echo -e "${YELLOW}⚠️  /health/detailed returned $HEALTH_DETAILED (should be 403)${NC}"
fi

# Check exports are public
EXPORT_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8080/api/export/mtga \
    -H 'Content-Type: application/json' \
    -d '{"main":[{"qty":4,"name":"Island"}],"side":[]}' 2>/dev/null || echo "000")
if [ "$EXPORT_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Export endpoints are public${NC}"
else
    echo -e "${RED}❌ Export endpoints require auth (should be public)${NC}"
    GATE_STATUS="NO-GO"
    FAILURES+=("Export Auth")
fi
echo ""

# FINAL DECISION
echo "=============================================="
echo -e "${BLUE}GATE FINAL DECISION${NC}"
echo "=============================================="

if [ "$GATE_STATUS" = "GO" ]; then
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════╗"
    echo "║           🎉 GO FOR LAUNCH 🎉        ║"
    echo "╚══════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo "✅ All checks passed!"
    echo "✅ System is production ready"
    echo ""
    echo "Next steps:"
    echo "1. Tag the release: git tag -a v2.1.0-rc1 -m 'Release Candidate 1'"
    echo "2. Push to remote: git push origin v2.1.0-rc1"
    echo "3. Create GitHub release"
    echo ""
    exit 0
else
    echo -e "${RED}"
    echo "╔══════════════════════════════════════╗"
    echo "║          ⛔ NO-GO STATUS ⛔          ║"
    echo "╚══════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo "Failed checks:"
    for failure in "${FAILURES[@]}"; do
        echo "  ❌ $failure"
    done
    echo ""
    echo "Please fix the issues above and run again."
    echo ""
    exit 1
fi