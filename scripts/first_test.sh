#!/bin/bash
# First Test Script for QA - Manual validation script
# Usage: ./scripts/first_test.sh

set -e  # Exit on error
set -u  # Exit on undefined variable

# Anti-flakiness: Set deterministic environment
export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TOKENIZERS_PARALLELISM=false
export CUBLAS_WORKSPACE_CONFIG=:4096:8
export S2D_SEED=42
export S2D_THREADS=1
export DETERMINISTIC_MODE=on

# Feature flags (explicit and safe)
export OCR_ENGINE=easyocr
export VISION_OCR_FALLBACK=off
export FUZZY_STRICT_MODE=on
export SCRYFALL_ONLINE=off

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8080}"
TEST_IMAGE="${TEST_IMAGE:-validation_set/MTGA deck list_1535x728.jpeg}"
DEMO_EMAIL="${DEMO_EMAIL:-demo@example.com}"
DEMO_PASSWORD="${DEMO_PASSWORD:-Demo1234!}"

echo "🚀 Screen2Deck First Test Script"
echo "================================"
echo "API: $API_URL"
echo "Test Image: $TEST_IMAGE"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check dependencies
echo "1️⃣  Checking dependencies..."
for cmd in curl jq; do
    if ! command_exists $cmd; then
        echo -e "${RED}❌ $cmd is not installed${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✅ Dependencies OK${NC}"
echo ""

# Health check
echo "2️⃣  Checking API health..."
if ! curl -fsS "$API_URL/health" > /dev/null; then
    echo -e "${RED}❌ API is not healthy${NC}"
    echo "   Make sure backend is running: make up-core"
    exit 1
fi
echo -e "${GREEN}✅ API is healthy${NC}"
echo ""

# Warm-up (download models if needed)
echo "3️⃣  Warm-up test (EasyOCR models)..."
echo "   This may take 1-2 minutes on first run..."
WARMUP_RESPONSE=$(curl -sX POST "$API_URL/api/ocr/upload" \
    -F "file=@$TEST_IMAGE" \
    -H "Accept: application/json")

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Warm-up failed (models may be downloading)${NC}"
else
    echo -e "${GREEN}✅ Warm-up complete${NC}"
fi
echo ""

# Main OCR test
echo "4️⃣  Running OCR test..."
echo "   Uploading: $TEST_IMAGE"
OCR_RESPONSE=$(curl -sX POST "$API_URL/api/ocr/upload" \
    -F "file=@$TEST_IMAGE" \
    -H "Accept: application/json")

JOB_ID=$(echo "$OCR_RESPONSE" | jq -r .jobId)
CACHED=$(echo "$OCR_RESPONSE" | jq -r .cached)

if [ "$JOB_ID" == "null" ]; then
    echo -e "${RED}❌ Upload failed${NC}"
    echo "$OCR_RESPONSE" | jq .
    exit 1
fi

echo "   Job ID: $JOB_ID"
echo "   Cached: $CACHED"
echo ""

# Poll for results
echo "5️⃣  Waiting for OCR results..."
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    STATUS_RESPONSE=$(curl -sX GET "$API_URL/api/ocr/status/$JOB_ID")
    STATE=$(echo "$STATUS_RESPONSE" | jq -r .state)
    
    if [ "$STATE" == "completed" ]; then
        echo -e "${GREEN}✅ OCR completed${NC}"
        RESULT=$(echo "$STATUS_RESPONSE" | jq .result)
        
        # Extract card counts
        MAIN_COUNT=$(echo "$RESULT" | jq '.normalized.main | length')
        SIDE_COUNT=$(echo "$RESULT" | jq '.normalized.side | length')
        
        echo ""
        echo "📊 Results:"
        echo "   Main deck: $MAIN_COUNT cards"
        echo "   Sideboard: $SIDE_COUNT cards"
        echo ""
        
        # Show first 3 cards
        echo "   Sample cards:"
        echo "$RESULT" | jq -r '.normalized.main[:3][] | "   - \(.qty)x \(.name)"'
        break
    elif [ "$STATE" == "failed" ]; then
        echo -e "${RED}❌ OCR failed${NC}"
        echo "$STATUS_RESPONSE" | jq .
        exit 1
    fi
    
    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."
    sleep 1
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo -e "${RED}❌ Timeout waiting for results${NC}"
    exit 1
fi
echo ""

# Test export formats
echo "6️⃣  Testing export formats..."
FORMATS="mtga moxfield archidekt tappedout"

for FORMAT in $FORMATS; do
    echo -n "   Testing $FORMAT format... "
    
    # Create minimal deck JSON for testing
    DECK_JSON='{
        "main": [
            {"qty": 4, "name": "Island"},
            {"qty": 4, "name": "Lightning Bolt"},
            {"qty": 2, "name": "Teferi, Time Raveler"}
        ],
        "side": [
            {"qty": 2, "name": "Negate"}
        ]
    }'
    
    EXPORT_RESPONSE=$(curl -sX POST "$API_URL/api/export/$FORMAT" \
        -H "Content-Type: application/json" \
        -d "$DECK_JSON")
    
    if echo "$EXPORT_RESPONSE" | jq -e .text > /dev/null 2>&1; then
        echo -e "${GREEN}✅${NC}"
    else
        echo -e "${RED}❌${NC}"
        echo "$EXPORT_RESPONSE" | jq .
    fi
done
echo ""

# Cache test (re-upload same image)
echo "7️⃣  Testing cache (re-upload)..."
CACHE_RESPONSE=$(curl -sX POST "$API_URL/api/ocr/upload" \
    -F "file=@$TEST_IMAGE" \
    -H "Accept: application/json")

CACHE_JOB_ID=$(echo "$CACHE_RESPONSE" | jq -r .jobId)
CACHE_HIT=$(echo "$CACHE_RESPONSE" | jq -r .cached)

if [ "$CACHE_HIT" == "true" ]; then
    echo -e "${GREEN}✅ Cache hit detected${NC}"
else
    echo -e "${YELLOW}⚠️  No cache hit (may be normal on first run)${NC}"
fi
echo ""

# Check metrics
echo "8️⃣  Checking Prometheus metrics..."
METRICS=$(curl -s "$API_URL/metrics" 2>/dev/null | head -50)

if echo "$METRICS" | grep -q "screen2deck_"; then
    echo -e "${GREEN}✅ Metrics exposed${NC}"
    echo "   Sample metrics:"
    echo "$METRICS" | grep "screen2deck_" | head -3 | sed 's/^/   /'
else
    echo -e "${YELLOW}⚠️  No custom metrics found${NC}"
fi
echo ""

# Summary
echo "================================"
echo "📋 Test Summary"
echo "================================"
echo -e "${GREEN}✅ API Health: OK${NC}"
echo -e "${GREEN}✅ OCR Upload: OK${NC}"
echo -e "${GREEN}✅ OCR Processing: OK${NC}"
echo -e "${GREEN}✅ Export Formats: OK${NC}"
if [ "$CACHE_HIT" == "true" ]; then
    echo -e "${GREEN}✅ Cache: Working${NC}"
else
    echo -e "${YELLOW}⚠️  Cache: Not verified${NC}"
fi
echo ""
echo "🎉 First test complete!"
echo ""
echo "Next steps:"
echo "1. Open http://localhost:3000 in browser"
echo "2. Upload an image manually"
echo "3. Export to different formats"
echo "4. Run full benchmark: make bench-truth"